"""pymonzo API client code."""
import webbrowser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from authlib.integrations.httpx_client import OAuth2Client

from pymonzo.accounts import AccountsResource
from pymonzo.attachments import AttachmentsResource
from pymonzo.balance import BalanceResource
from pymonzo.feed import FeedResource
from pymonzo.pots import PotsResource
from pymonzo.settings import PyMonzoSettings
from pymonzo.transactions import TransactionsResource
from pymonzo.utils import get_authorization_response
from pymonzo.webhooks import WebhooksResource
from pymonzo.whoami import WhoAmIResource


class MonzoAPI:
    """Monzo public API client.

    To use it, you need to create a new OAuth client in
    [Monzo Developer Portal](https://developers.monzo.com/). The `Redirect URLs`
    should be set to `http://localhost:6600/pymonzo` and `Confidentiality` should
    be set to `Confidential` if you'd like to automatically refresh the access token
    when it expires.

    You can now use `Client ID` and `Client secret` in [`pymonzo.MonzoAPI.authorize`][]
    to finish the OAuth 2 'Authorization Code Flow' and get the API access token
    (which is by default saved to disk and refreshed when expired).

    Note:
        Monzo API docs: https://docs.monzo.com/
    """

    api_url = "https://api.monzo.com"
    authorization_endpoint = "https://auth.monzo.com/"
    token_endpoint = "https://api.monzo.com/oauth2/token"  # noqa
    settings_path = Path.home() / ".pymonzo"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token: Optional[dict] = None,
    ) -> None:
        """Initialize Monzo API client and mount all resources.

        It expects [`pymonzo.MonzoAPI.authorize`][] to be called beforehand, so
        it can load the local settings file containing the API access token. You
        can also explicitly pass `client_id`, `client_secret` and `token` values.

        Arguments:
            client_id: OAuth client ID.
            client_secret: OAuth client secret.
            token: OAuth access token. For more information see
                [`pymonzo.MonzoAPI.authorize`][].

        Raises:
            ValueError: When client ID and secret weren't passed explicitly and
                settings file could not be loaded.
        """
        if client_id and client_secret and token:
            self._settings = PyMonzoSettings(
                client_id=client_id,
                client_secret=client_secret,
                token=token,
            )
        else:
            try:
                self._settings = PyMonzoSettings.load_from_disk(self.settings_path)
            except FileNotFoundError as e:
                raise ValueError(
                    "You need to run `MonzoAPI.authorize(client_id, client_secret)` "
                    "to get the authorization token and save it to disk, or explicitly"
                    "pass the `client_id`, `client_secret` and `token` arguments."
                ) from e

        self.session = OAuth2Client(
            client_id=self._settings.client_id,
            client_secret=self._settings.client_secret,
            token=self._settings.token,
            authorization_endpoint=self.authorization_endpoint,
            token_endpoint=self.token_endpoint,
            update_token=self._update_token,
            base_url=self.api_url,
        )

        self.whoami = WhoAmIResource(client=self).whoami
        """
        Mounted Monzo `whoami` endpoint. For more information see
        [`pymonzo.whoami.WhoAmIResource.whoami`][].
        """

        self.accounts = AccountsResource(client=self)
        """
        Mounted Monzo `accounts` resource. For more information see
        [`pymonzo.accounts.AccountsResource`][].
        """

        self.attachments = AttachmentsResource(client=self)
        """
        Mounted Monzo `attachments` resource. For more information see
        [`pymonzo.attachments.AttachmentsResource`][].
        """

        self.balance = BalanceResource(client=self)
        """
        Mounted Monzo `balance` resource. For more information see
        [`pymonzo.balance.BalanceResource`][].
        """

        self.feed = FeedResource(client=self)
        """
        Mounted Monzo `feed` resource. For more information see
        [`pymonzo.feed.FeedResource`][].
        """

        self.pots = PotsResource(client=self)
        """
        Mounted Monzo `pots` resource. For more information see
        [`pymonzo.pots.PotsResource`][].
        """

        self.transactions = TransactionsResource(client=self)
        """
        Mounted Monzo `transactions` resource. For more information see
        [`pymonzo.transactions.TransactionsResource`][].
        """

        self.webhooks = WebhooksResource(client=self)
        """
        Mounted Monzo `webhooks` resource. For more information see
        [`pymonzo.webhooks.WebhooksResource`][].
        """

    @classmethod
    def authorize(
        cls,
        client_id: str,
        client_secret: str,
        *,
        save_to_disk: bool = True,
        redirect_uri: str = "http://localhost:6600/pymonzo",
    ) -> dict:
        """Use OAuth 2 'Authorization Code Flow' to get Monzo API access token.

        By default, it also saves the token to disk, so it can be loaded during
        [`pymonzo.MonzoAPI`][] initialization.

        Note:
            Monzo API docs: https://docs.monzo.com/#authentication

        Arguments:
            client_id: OAuth client ID.
            client_secret: OAuth client secret.
            save_to_disk: Whether to save the token to disk.
            redirect_uri: Redirect URI specified in OAuth client.

        Returns:
            OAuth access token.
        """
        client = OAuth2Client(client_id, client_secret, redirect_uri=redirect_uri)
        url, state = client.create_authorization_url(cls.authorization_endpoint)

        print(f"Please visit this URL to authorize: {url}")  # noqa
        webbrowser.open(url)

        # Start a webserver and wait for the callback
        parsed_url = urlparse(redirect_uri)
        assert parsed_url.hostname is not None
        assert parsed_url.port is not None
        authorization_response = get_authorization_response(
            host=parsed_url.hostname,
            port=parsed_url.port,
        )

        token = client.fetch_token(
            cls.token_endpoint,
            authorization_response=authorization_response,
        )

        # Save settings to disk
        if save_to_disk:
            settings = PyMonzoSettings(
                client_id=client_id,
                client_secret=client_secret,
                token=token,
            )
            settings.save_to_disk(cls.settings_path)

        return token

    def _update_token(self, token: dict, **kwargs: Any) -> None:
        """Update settings with refreshed access token and save it to disk.

        Arguments:
            token: OAuth access token.
            **kwargs: Extra kwargs.
        """
        self._settings.token = token
        if self.settings_path.exists():
            self._settings.save_to_disk(self.settings_path)
