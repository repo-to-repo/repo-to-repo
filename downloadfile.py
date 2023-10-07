import logging
import requests
from getgithubrelease import GithubAsset
from consolidateconfig import ConsolidateConfig

class DownloadFile:
    def __init__(self, asset: GithubAsset, config: ConsolidateConfig, target: str):
        logging.debug('DownloadFile:__init__')
        self.target = target
        self.config = config

        headers = {}
        if self.config.exists('headers') and self.config.get('headers') != '':
            headers = self.config.get('headers')

        logging.debug(f"Getting asset: {asset.name} from {asset.url}")
        response = requests.get(asset.url, headers=headers)
        if response.status_code == 200:
            with open(f"{target}", 'wb') as file:
                file.write(response.content)
            logging.debug(f"File downloaded to {target}")
        else:
            raise FileNotFoundError("Failed to download the file.")
            
    def getTarget(self):
        logging.debug('DownloadFile:getTarget')
        return self.target