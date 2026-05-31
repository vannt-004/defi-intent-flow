from web3 import Web3


class MulticallClient:
    MULTICALL_ABI = [
        {
            "inputs": [
                {
                    "components": [
                        {
                            "name": "target", "type": "address"
                        }, {
                            "name": "callData", "type": "bytes"
                        }
                    ], "name": "calls", "type": "tuple[]"
                }
            ], "name": "aggregate", "outputs": [
            {
                "name": "blockNumber", "type": "uint256"
            }, {
                "name": "returnData", "type": "bytes[]"
            }
        ], "stateMutability": "view", "type": "function"
        }
    ]

    ERC20_ABI = [
        {
            "name": "balanceOf",
            "type": "function",
            "stateMutability": "view",
            "inputs": [
                {
                    "name": "owner", "type": "address"
                }
            ],
            "outputs": [
                {
                    "type": "uint256"
                }
            ]
        }
    ]

    def __init__(self, w3: Web3, multicall_address: str):
        self.w3 = w3

        self.multicall = w3.eth.contract(address=Web3.to_checksum_address(multicall_address), abi=self.MULTICALL_ABI)

    def execute(self, calls):
        _, return_data = (self.multicall.functions.aggregate(calls).call())

        return return_data
