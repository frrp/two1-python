import os.path
import collections

from . import wallet as walletwrapper
from . import database
from . import blockchain
from . import paymentchannel


PaymentChannelStatus = collections.namedtuple('PaymentChannelStatus', ['url', 'state', 'ready', 'balance', 'deposit', 'fee', 'creation_time', 'expiration_time', 'expired', 'deposit_txid', 'spend_txid'])
"""Container for the status information of a payment channel."""


class NotFoundError(IndexError):
    """Channel not found error."""
    pass


class PaymentChannelClient:
    """"Payment channel client."""

    DEFAULT_CHANNELS_DB_PATH = os.path.expanduser('~/.two1/channels/channels.sqlite3')
    """Default payment channel database path."""

    DEFAULT_INSIGHT_BLOCKCHAIN_URL = "https://blockexplorer.com"
    """Default mainnet blockchain URL."""

    DEFAULT_INSIGHT_TESTNET_BLOCKCHAIN_URL = "https://testnet.blockexplorer.com"
    """Default testnet blockchain URL."""

    def __init__(self, wallet, db_path=DEFAULT_CHANNELS_DB_PATH):
        """Instantiate a payment channel client with the specified wallet and
        channel database.

        Args:
            wallet (two1.lib.wallet.Wallet): Instance of the two1 wallet.
            db_path (str): Payment channel database path.

        Returns:
            PaymentChannelClient: instance of PaymentChannelClient.

        """
        self._wallet = walletwrapper.Two1WalletWrapper(wallet)
        self._database = database.Sqlite3Database(db_path)
        self._blockchain = blockchain.InsightBlockchain(PaymentChannelClient.DEFAULT_INSIGHT_BLOCKCHAIN_URL if not wallet.testnet else PaymentChannelClient.DEFAULT_INSIGHT_TESTNET_BLOCKCHAIN_URL)

        self._channels = collections.OrderedDict()
        self._update_channels()

    def _update_channels(self):
        # Look up and add new channels to our channels list
        with self._database:
            for url in self._database.list():
                if url not in self._channels:
                    self._channels[url] = paymentchannel.PaymentChannel(url, self._database, self._wallet, self._blockchain)

    def open(self, url, deposit, expiration, fee=10000, zeroconf=False, use_unconfirmed=False):
        """Open a payment channel at the specified URL.

        Args:
            url (str): Payment channel server URL.
            deposit (int): Deposit amount in satoshis.
            expiration (int): Relative expiration time in seconds.
            fee (int): Fee in in satoshis.
            zeroconf (bool): Use payment channel without deposit confirmation.
            use_unconfirmed (bool): Use unconfirmed transactions to build
                deposit transaction.

        Returns:
            str: Payment channel URL.

        Raises:
            InsufficientBalanceError: If wallet has insufficient balance to
                make deposit for payment channel.

        """
        with self._database.lock:
            # Open the payment channel
            channel = paymentchannel.PaymentChannel.open(self._database, self._wallet, self._blockchain, url, deposit, expiration, fee, zeroconf, use_unconfirmed)

            # Add it to our channels dictionary
            self._channels[channel.url] = channel

            return channel.url

    def sync(self, url=None):
        """Synchronize one or more payment channels with the blockchain.

        Update the payment channel in the cases of deposit confirmation or
        deposit spend, and refund the payment channel in the case of channel
        expiration.

        Args:
            url (str or None): Optional URL to limit synchronization to.

        Raises:
            NotFoundError: If the payment channel was not found.

        """
        with self._database.lock:
            # Update channels
            self._update_channels()

            if url:
                if url not in self._channels:
                    raise NotFoundError("Channel not found.")

                # Sync channel
                self._channels[url].sync()
            else:
                # Sync all channels
                for channel in self._channels.values():
                    channel.sync()

    def pay(self, url, amount):
        """Pay to the payment channel.

        Args:
            url (str): Payment channel URL.
            amount (int): Amount to pay in satoshis.

        Returns:
            str: Redeemable token for the payment.

        Raises:
            NotFoundError: If the payment channel was not found.
            NotReadyError: If payment channel is not ready for payment.
            InsufficientBalanceError: If payment channel balance is
                insufficient to pay.
            ClosedError: If payment channel is closed or was closed by server.
            PaymentChannelError: If an unknown server error occurred.

        """
        with self._database.lock:
            if url not in self._channels:
                raise NotFoundError("Channel not found.")

            # Pay to channel
            return self._channels[url].pay(amount)

    def status(self, url):
        """Get payment channel status and information.

        Args:
            url (str): Payment channel URL.

        Returns:
            PaymentChannelStatus: Named tuple with url (str), state
                (PaymentChannelState), ready (bool), balance (int, satoshis),
                deposit (int, satoshis), fee (int, satoshis), creation_time
                (float, UNIX time), expiration_time (int, UNIX time), expired
                (bool), deposit_txid (str), spend_txid (str).

        """
        with self._database.lock:
            if url not in self._channels:
                raise NotFoundError("Channel not found.")

            # Get channel status
            channel = self._channels[url]
            return PaymentChannelStatus(
                url=channel.url,
                state=channel.state,
                ready=channel.ready,
                balance=channel.balance,
                deposit=channel.deposit,
                fee=channel.fee,
                creation_time=channel.creation_time,
                expiration_time=channel.expiration_time,
                expired=channel.expired,
                deposit_txid=channel.deposit_txid,
                spend_txid=channel.spend_txid
            )

    def close(self, url):
        """Close the payment channel.

        Args:
            url (str): Payment channel URL.

        Raises:
            NotFoundError: If the payment channel was not found.
            NotReadyError: If payment channel is not ready.
            NoPaymentError: If payment channel has no payments.

        """
        with self._database.lock:
            if url not in self._channels:
                raise NotFoundError("Channel not found.")

            self._channels[url].close()

    def list(self, url=None):
        """Get a list of payment channel URLs.

        Args:
            url (str or None): Optional URL to limit channels to.

        Returns:
            list: List of urls (str), sorted by readiness.

        """
        with self._database.lock:
            # Update channels
            self._update_channels()

            if url:
                urls = [channel_url for channel_url in self._channels.keys() if channel_url.startswith(url)]
            else:
                urls = list(self._channels.keys())

            return sorted(urls, key=lambda url: (self._channels[url].ready, self._channels[url].balance, self._channels[url].creation_time), reverse=True)