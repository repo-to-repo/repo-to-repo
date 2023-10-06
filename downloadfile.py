import logging
import requests
import re
from getgithubrelease import GithubAsset

class DownloadFile:
    def __init__(self, asset: GithubAsset, target: str):
        logging.debug('DownloadFile:__init__')
        self.target = target
        logging.debug(f"Getting asset: {asset.name} from {asset.url}")
        response = requests.get(asset.url)
        if response.status_code == 200:
            with open(f"{target}", 'wb') as file:
                file.write(response.content)
            logging.debug(f"File downloaded to {target}")
        else:
            raise FileNotFoundError("Failed to download the file.")
            
    def getTarget(self):
        logging.debug('DownloadFile:getTarget')
        return self.target