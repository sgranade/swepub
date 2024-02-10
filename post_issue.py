import tomllib
from contextlib import suppress
from datetime import date, datetime, timedelta
from enum import StrEnum, auto
from pathlib import Path
from urllib.parse import urljoin

import click
import pytz
import requests

from issue_info import IssueInfo, get_issue_info


class REST(StrEnum):
    GET = auto()
    PUT = auto()
    POST = auto()


class NAMESPACES(StrEnum):
    WP = "wp/v2/"
    JWT = "jwt-auth/v1"
    RML = "realmedialibrary/v1/"


# TODO REMOVE AFTER TESTING
VERIFY = False

import urllib3

urllib3.disable_warnings()
# TODO END REMOVE AFTER TESTING


def warn(s: str) -> None:
    """Print a warning to the console."""
    click.secho(s, bold=True)


def response_jwt_error(r: requests.Response) -> str | None:
    """Get the JWT-returned error from a request, if available.

    The code will be from the `code` key in the JSON payload,
    either from "[jwt_auth] <code>" or "<code>" where the code
    starts with `jwt_`.

    :param r: Response from requests.
    :return: The error code, or None if no code found.
    """
    error = None
    with suppress(requests.JSONDecodeError):
        code = r.json().get("code", None)
        if code:
            if code.startswith("[jwt_auth]"):
                error = code.removeprefix("[jwt_auth]").strip()
            elif code.startswith("jwt_"):
                error = code.strip()
    return error


def response_reason(r: requests.Response) -> str:
    """Get the reason from a response."""
    # See if there's a json payload with a message
    try:
        reason = r.json()["message"]
    except (requests.JSONDecodeError, KeyError, TypeError):
        if isinstance(r.reason, bytes):
            # We attempt to decode utf-8 first because some servers
            # choose to localize their reason strings. If the string
            # isn't utf-8, we fall back to iso-8859-1 for all other
            # encodings. (See PR #3538)
            try:
                reason = r.reason.decode("utf-8")
            except UnicodeDecodeError:
                reason = r.reason.decode("iso-8859-1")
        else:
            reason = r.reason
    return reason


def check_response(r: requests.Response, task_desc: str | None = None) -> None:
    """Raise an error if a response's code indicates a client or server error.

    :param r: Response object from a requests call.
    :param task_desc: Optional description of the task being performed.
    """
    http_error_msg = ""
    if task_desc is None:
        task_desc = ""
    else:
        task_desc = f"Error {task_desc}. "
    reason = response_reason(r)

    if 400 <= r.status_code < 500:
        http_error_msg = (
            f"{task_desc}{r.status_code} Client Error: {reason} for url: {r.url}"
        )

    elif 500 <= r.status_code < 600:
        http_error_msg = (
            f"{task_desc}{r.status_code} Server Error: {reason} for url: {r.url}"
        )

    if http_error_msg:
        raise requests.HTTPError(http_error_msg, response=r)


def get_token(username: str, password: str) -> str:
    """Fetch a JWT token from a WP host.

    :param username: WordPress user's username.
    :param password: WordPress user's password.
    :return: The token.
    :raises HTTPError: If the token can't be fetched.
    """
    rest_endpoint = wp_rest_url("token", NAMESPACES.JWT)
    resp = requests.post(
        rest_endpoint, json={"username": username, "password": password}, verify=VERIFY
    )
    if resp.status_code != 200:
        raise requests.HTTPError(
            f"Failed to get JWT token. {resp.status_code} error: {response_reason(resp)} for url: {resp.url}",
            response=resp,
        )
    j = resp.json()
    return j["token"]


def verify_token(token: str) -> None:
    """Verify a JWT token.

    :param token: JWT token value.
    :raises HTTPError: If the token doesn't validate.
    """
    rest_endpoint = wp_rest_url("token/validate", NAMESPACES.JWT)
    resp = requests.post(
        rest_endpoint, headers={"Authorization": f"Bearer {token}"}, verify=VERIFY
    )
    check_response(resp, "validating a token")


host_info: dict[str, str | None] = None
"""Information about the host."""

current_token: str = None
"""JSON Web Token for authentication."""

rml_folders: dict[str, int] = None
"""Real Media Library folders' names and their corresponding IDs."""


def setup_host_info(config_file: Path = Path("issue_config.toml")) -> None:
    """Gets host info from a config file and the user and saves it in host_info.

    Host info is first loaded from a config file. The user is prompted for missing info.

    :param file: Config file to load, defaults to Path("issue_config.toml")
    """
    global host_info

    if not config_file.is_absolute():
        config_file = Path(__file__).parent / config_file
    try:
        defaults = tomllib.loads(config_file.read_text("utf-8"))
    except tomllib.TOMLDecodeError as e:
        click.echo(f"Couldn't open config file {config_file}. {e}")
        defaults = {}
    host = defaults.get("host", None)
    username = defaults.get("username", None)
    password = defaults.get("password", None)
    use_2fa = defaults.get("use_2fa", None)
    if host is None:
        host = click.prompt("Enter the URL to your WordPress site", type=str)
    if username is None:
        username = click.prompt("Enter your WordPress username", type=str)
    if password is None:
        password = click.prompt("Enter your WordPress password", type=str)
    host_info = {
        "host": host,
        "username": username,
        "password": password,
        "use_2fa": use_2fa,
    }


def setup_token() -> None:
    """Set up our JWT for authentication."""
    global current_token

    if host_info["password"] is None:
        host_info["password"] = click.prompt("Enter your WordPress password", type=str)
    if host_info["use_2fa"] is True:
        twofactor = click.prompt("Enter your 2FA code", type=str)
    else:
        twofactor = ""

    while True:
        try:
            current_token = get_token(
                host_info["username"],
                host_info["password"] + twofactor,
            )
            break
        except requests.HTTPError as e:
            code = response_jwt_error(e.response)
            if code == "invalid_username":
                host_info["username"] = click.prompt(
                    f"Invalid username {host_info['username']}. Enter your WordPress username",
                    type=str,
                )
            elif code == "incorrect_password":
                warn(f"Failed to authenticate user {host_info['username']}")
                host_info["password"] = click.prompt(
                    f"Wrong password for user {host_info['username']}. Enter your WordPress password",
                    type=str,
                )
            elif code == "wfls_twofactor_required":
                host_info["use_2fa"] = True
                twofactor = click.prompt("Enter your 2FA code", type=str)
            else:
                raise


def setup_rml_folders() -> None:
    """Set up information about Real Media Library folders on the WP site."""
    global rml_folders

    r = wp_request(
        REST.GET,
        "tree",
        "getting information about Real Media Library folders",
        rest_namespace="realmedialibrary/v1/",
    )
    if r.status_code == 200:
        rml_folders = {
            folder["name"].lower(): folder["id"] for folder in r.json()["tree"]
        }
    elif r.status_code == 404:
        warn("No Real Media Library folders found on the site")
        rml_folders = {}
    else:
        check_response(r, "getting information about Real Media Library folders")


def make_token_headers(headers: dict | None = None) -> dict:
    """Get the headers to authorize with a JSON web token.

    Requires current_token to be set up.

    :param token: JWT.
    :param headers: Previous headers to add the authorization header to.
    :return: The updated headers.
    """
    global current_token

    if headers is None:
        headers = {}

    headers["Authorization"] = f"Bearer {current_token}"

    return headers


def get_wp_headers(headers: dict[str, str] | None = None) -> None:
    """Get headers for communicating with WordPress, including our JWT.

    :param headers: Headers to add WP headers to, defaults to None
    :return: Full headers
    """
    if headers is None:
        headers = {}
    return make_token_headers(headers)


def wp_rest_url(endpoint: str, namespace: str = NAMESPACES.WP) -> str:
    """Create a full WordPress REST URL from the endpoint.

    The host information must be set up before calling this function.

    :param endpoint: Endpoint such as "media" or "posts".
    :param namespace: Namespace for the endpoint.
    :return: The full URL to the REST endpoint.
    """
    if namespace[-1] != "/":
        namespace += "/"
    if endpoint[0] == "/":
        endpoint = endpoint[1:]
    return urljoin(urljoin(urljoin(host_info["host"], "wp-json/"), namespace), endpoint)


def wp_request(
    verb: REST,
    endpoint: str,
    task_desc: str | None = None,
    *,
    params: dict[str, str] | None = None,
    data: dict | list | bytes | None = None,
    json: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    rest_namespace: str | None = None,
) -> requests.Response:
    """Perform a REST request to a WordPress site.

    :param verb: Type of request to perform.
    :param endpoint: REST endpoint to get.
    :param task_desc: Description of the task being performed, defaults to None.
    :param params: Additional request parameters, defaults to None
    :param data: Data to send in the body, defaults to None.
    :param json: JSON-izeable object to send in the body, defaults to None.
    :param headers: Headers for the request, defaults to None.
    :param rest_namespace: Namespace for the REST request, or None to use the default.
    :return: Response
    """
    h = get_wp_headers(headers)
    if rest_namespace:
        full_endpoint = wp_rest_url(endpoint, rest_namespace)
    else:
        full_endpoint = wp_rest_url(endpoint)

    while True:
        r = requests.request(
            verb,
            full_endpoint,
            headers=h,
            params=params,
            data=data,
            json=json,
            verify=VERIFY,
        )
        if r.status_code == 403:
            code = response_jwt_error(r)
            if code == "jwt_auth_invalid_token":
                warn("JWT token has expired.")
                setup_token()
                h = get_wp_headers(headers)
                continue
        check_response(r, task_desc)
        break

    return r


def issue_release_time(year_month: date | None = None) -> datetime:
    """Get the release time for an issue.

    Issues are released on the first Monday of a month at 11:00 am CDT.

    :param year_month: Year and month to release the issue. If None, it's automatically set to the month following the current one.
    :return: The next month's first Monday.
    """
    # Start with the first day of the month
    dt = datetime.utcnow().replace(day=1, hour=11, minute=0, second=0, microsecond=0)
    if year_month is not None:
        dt = dt.replace(year=year_month.year, month=year_month.month)
    else:
        # Skip forward to the first day of next month
        dt = (dt + timedelta(days=32)).replace(day=1)

    # Now move to the first Monday and adjust the timezone
    tz_delta = pytz.timezone("America/Chicago").utcoffset(dt)
    dt += timedelta(days=7 - dt.weekday()) - tz_delta

    return dt


def get_existing_wp_object_by_slug(
    obj_name: str, endpoint: str, slug: str
) -> int | None:
    """See if a WP object exists and, if so, get its ID.

    :param obj_name: Descriptive name of the object, like "cover".
    :param endpoint: WP REST endpoint to query.
    :param slug: Slug to search for.
    :return: ID if found, or None if not.
    """
    obj_id = None
    params = {"slug": slug}
    # Non-media endpoints may be published or future-scheduled
    if endpoint != "media":
        params["status"] = "publish,future"
    resp = wp_request(
        REST.GET,
        endpoint,
        f"checking for an existing {obj_name}",
        params=params,
    )
    json = resp.json()
    if json:
        if len(json) > 1:
            raise RuntimeError(
                f"When looking for an existing {obj_name}, we found multiple ones "
                f"with the slug {slug}: "
                ", ".join(
                    [f"{obj['title']['rendered']} (id {obj['id']})" for obj in json]
                )
            )
        else:
            obj_id = json[0]["id"]
            click.echo(
                f"{obj_name.capitalize()} has already been created (id {obj_id}); skipping."
            )

    return obj_id


def upload_image(
    img: Path,
    filename: str | None = None,
    title: str | None = None,
    alt_text: str | None = None,
    slug: str | None = None,
) -> int:
    """Upload an image to the WP site.

    :param img: Path to the image file in jpeg format.
    :param filename: Filename to give the image on the WP site, defaults to None
    :param title: Title to give the image on the WP site, defaults to None
    :param alt_text: Image alt text, defaults to None
    :param slug: WP slug to the image, defaults to None
    :return: ID of the uploaded image.
    """
    if filename is None:
        filename = img.name
    img_bytes = img.read_bytes()

    headers = {
        "Content-Type": "image/jpeg",
        "Accept": "application/json",
        "Content-Disposition": f"attachment; filename={filename}",
    }
    resp = wp_request(
        REST.POST,
        "media",
        "uploading an image",
        data=img_bytes,
        headers=headers,
    )

    img_id = int(resp.json()["id"])

    if title or alt_text or slug:
        post_info = {}
        if title:
            post_info["title"] = title
        if alt_text:
            post_info["alt_text"] = alt_text
        if slug:
            post_info["slug"] = slug
        resp = wp_request(
            REST.POST,
            f"media/{img_id}",
            "updating the image metadata",
            json=post_info,
        )

    return img_id


def move_image_to_rml_folder(id: int, folder: str) -> None:
    """Move an image on the WP site to a Real Media Library folder.

    Prints a warning if the folder doesn't exist.

    :param id: ID of the uploaded media.
    :param folder: Name of the folder to move it to.
    """
    cover_folder_id = rml_folders.get(folder, None)
    if cover_folder_id is None:
        warn(
            f"No folder '{folder}' found in the site's Real Media Library. Available folders: {', '.join(rml_folders.keys)}"
        )
    else:
        r = wp_request(
            REST.PUT,
            "attachments/bulk/move",
            f"moving an image to the Real Media Folder {folder} folder",
            json={"ids": [id], "to": int(cover_folder_id), "isCopy": False},
            rest_namespace=NAMESPACES.RML,
        )
        check_response(r)


def create_cover(info: IssueInfo) -> int:
    """Create the issue's cover image on the WordPress site.

    :param info: Information about the issue.
    :return: The WP ID of the cover image.
    """
    global rml_folders

    title = f"Issue {info.issue_num}"
    slug = f"sw_cover_issue_{info.issue_num}"

    cover_id = get_existing_wp_object_by_slug("cover", "media", slug)
    if cover_id is None:
        click.echo("Uploading cover image.")
        cover_id = upload_image(
            info.cover_path,
            f"SW_Cover_Issue{info.issue_num:02}.jpg",
            title,
            f"Issue {info.issue_num} cover",
            slug,
        )
        move_image_to_rml_folder(cover_id, "covers")

    return cover_id


def create_issue_info(info: IssueInfo, cover_id: int, post_date: datetime) -> int:
    """Create the issue.

    :param info: Information about the issue.
    :param cover_id: The WP ID of the cover image.
    :param post_date: The date that the issue will post.
    :return: The WP ID of the issue.
    """
    title = f"Issue {info.issue_num}"
    slug = str(info.issue_num)

    issue_id = get_existing_wp_object_by_slug("issue", "issue", slug)
    if issue_id is None:
        click.echo("Creating issue.")
        resp = wp_request(
            REST.POST,
            "issue",
            "creating the issue",
            json={
                "title": title,
                "slug": slug,
                "featured_media": cover_id,
                "status": "future",
                "date_gmt": post_date.isoformat(),
            },
        )
        issue_id = int(resp.json()["id"])

    return issue_id


def create_issue(info: IssueInfo, post_date: datetime) -> int:
    """Create (or update) the issue on the WordPress site.

    :param info: Information about the issue.
    :post_date: Date when the issue will be posted.
    :return: ID for the issue.
    """
    cover_id = create_cover(info)
    return create_issue_info(info, cover_id, post_date)


def setup() -> None:
    """Perform necessary setup steps."""
    setup_host_info()
    setup_token()
    setup_rml_folders()


@click.command()
@click.option(
    "--content-path",
    help="Path to the content files",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--release-month",
    help="Date to release, in the format YYYY-MM",
    type=click.DateTime("%Y-%m"),
)
def post_issue(content_path: Path | None, release_month: datetime | None) -> None:
    root_path = Path(__file__).parent
    if not content_path:
        content_path = root_path / "content"

    info = get_issue_info(content_path)

    if release_month:
        release_month = release_month.date()
    release_date = issue_release_time(release_month)

    setup()

    issue_id = create_issue(info, release_date)

    # For each piece:
    # - create/update author
    # - upload/update the story/poem


if __name__ == "__main__":
    post_issue()
