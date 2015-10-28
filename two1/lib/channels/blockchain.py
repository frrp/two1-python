import requests


class BlockchainError(Exception):
    """Base class for Blockchain errors."""
    pass


class BlockchainServerError(BlockchainError):
    """Blockchain server error."""
    pass


class BlockchainBase:
    """Base class for a Blockchain interface."""

    def __init__(self):
        pass

    def check_confirmed(self, txid, num_confirmations=1):
        """Check that transaction txid has num_confirmations confirmations.

        Args:
            txid (str): Transaction ID (RPC byte order).
            num_confirmations (int): Number of confirmations.

        Returns:
            bool: True if confirmed, False if not confirmed.

        """
        raise NotImplementedError()

    def lookup_spend_txid(self, txid, output_index):
        """Look up the transaction txid that spent output index output_index of
        transaction txid.

        Args:
            txid (str): Transaction ID (RPC byte order).
            output_index (int): Output index (0-based).

        Returns:
            str: Transaction ID (RPC byte order) or None.

        """
        raise NotImplementedError()

    def lookup_tx(self, txid):
        """Look up a raw transaction by transaction txid.

        Args:
            txid (str): Transaction ID (RPC byte order).

        Returns:
            str: Serialized transaction or None.

        """
        raise NotImplementedError()

    def broadcast_tx(self, tx):
        """Broadcast serialized transaction.

        Args:
            tx (str): Serialized transaction (ASCII hex).

        """
        raise NotImplementedError()


class InsightBlockchain(BlockchainBase):
    """Blockchain interface to an Insight API."""

    def __init__(self, base_url):
        """Instantiate a Insight blockchain interface with specified URL.

        Args:
            base_url (str): Insight API URL.

        Returns:
            InsightBlockchain: instance of InsightBlockchain.

        """
        super().__init__()
        self._base_url = base_url

    def check_confirmed(self, txid, num_confirmations=1):
        # Get transaction info
        r = requests.get(self._base_url + "/api/tx/" + txid)
        if r.status_code == 404:
            return False
        elif r.status_code != 200:
            raise BlockchainServerError("Getting transaction info: Status Code {}, {}".format(r.status_code, r.text))

        # Check confirmation
        tx_info = r.json()
        return "confirmations" in tx_info and tx_info["confirmations"] >= num_confirmations

    def lookup_spend_txid(self, txid, output_index):
        # Get transaction info
        r = requests.get(self._base_url + "/api/tx/" + txid)
        if r.status_code == 404:
            return None
        elif r.status_code != 200:
            raise BlockchainServerError("Getting transaction info: Status Code {}, {}".format(r.status_code, r.text))

        # Validate utxo index is in bounds
        tx_info = r.json()
        if len(tx_info['vout']) <= output_index:
            raise ValueError("Output index out of bounds.")

        # If spent transaction exists
        if "spentTxId" in tx_info['vout'][output_index]:
            return tx_info['vout'][output_index]['spentTxId']

        return None

    def lookup_tx(self, txid):
        # Get raw transaction
        r = requests.get(self._base_url + "/api/rawtx/" + txid)
        if r.status_code == 404:
            return None
        elif r.status_code != 200:
            raise BlockchainServerError("Getting raw transaction: Status Code {}, {}".format(r.status_code, r.text))

        return r.json()['rawtx']

    def broadcast_tx(self, tx):
        # Broadcast transaction
        r = requests.post(self._base_url + "/api/tx/send", data={'rawtx': tx})
        if r.status_code != 200:
            raise BlockchainServerError("Broadcasting transaction: Status Code {}, {}".format(r.status_code, r.text))

        return r.json()['txid']