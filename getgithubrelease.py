import logging
import requests
import re
from consolidateconfig import ConsolidateConfig

class GetGithubRelease:
    def __init__(self, config: ConsolidateConfig):
        logging.debug('GetGithubRelease:__init__')
        self.config        = config
        self.owner         = ''
        self.repo          = ''
        self.version_match = ''
        self.object_regex  = ''
        self.latest        = True
        self.headers       = {}
        
        if self.config.exists('headers') and self.config.get('headers') != '':
            self.headers = self.config.get('headers')
        if self.config.exists('owner') and self.config.get('owner') != '':
            logging.debug("Setting owner from config")
            self.owner               = self.config.get('owner')
        if self.config.exists('repo') and self.config.get('repo') != '':
            logging.debug("Setting repo from config")
            self.repo                = self.config.get('repo')
        if self.config.exists('version_match'):
            logging.debug("Setting version match from config")
            self.version_match       = self.config.get('version_match')
            self.latest              = False
        if self.config.exists('object_regex'):
            logging.debug("Setting object_regex from config")
            self.object_regex        = self.config.get('object_regex')

        if self.owner == "" or self.repo == "":
            logging.error("Owner or Repo_name are empty")
            exit(1)

        logging.debug(f"owner: {self.owner}, repo: {self.repo}, version_match: {self.version_match}, latest: {self.latest}, object_regex: {self.object_regex}")

    def getRelease(self, page: int=1) -> dict:
        logging.debug('GetGithubRelease:getRelease')
        github_api_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/releases?page={page}'
        if self.latest:
            github_api_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest'
        else:
            logging.info("Asking Github for a list of all releases.")

        try:
            logging.debug(f"Getting API {github_api_url}")
            response = requests.get(github_api_url, headers=self.headers)
        except:
            logging.error("Unable to load github api")
            exit(1)        

        if response.status_code != 200:
            logging.error(f"Failed to retrieve data from GitHub API. Status code: {response.status_code}")
            exit(1)

        data = response.json()
        if self.latest:
            logging.debug(f"latest - data: {data}")
            return data
        else:
            for entry in data:
                tag = entry['tag_name']
                logging.debug(f"{tag} - data: {entry}")
                if self.version_match != '':
                    if tag.startswith(self.version_match):
                        return entry
                        break
                else:
                    return entry
                    break
        
        if len(data) > 0:
            return self.getRelease(page+1)
        raise RecursionError("Failed to get a release")

    def GetAssets(self) -> dict:
        logging.debug('GetGithubRelease:GetAssets')
        release = self.getRelease()
        assets = {}
        if 'assets' in release:
            for asset in release['assets']:
                if self.object_regex != '':
                    match = re.match(self.object_regex, asset['name'])
                    if match:
                        assets[asset['name']] = GithubAsset(asset['name'], asset['browser_download_url'], release['tag_name'], release['published_at'])
                else:
                    assets[asset['name']] = GithubAsset(asset['name'], asset['browser_download_url'], asset['tag_name'], release['published_at'])

        return assets
    
class GithubAsset:
    def __init__(self, name, url, tag, release_date):
        logging.debug('GithubAsset:__init__')
        self.name = name
        self.url = url
        self.tag = tag
        self.release_date = release_date

    def name(self):
        logging.debug('GithubAsset:name')
        return self.name

    def url(self):
        logging.debug('GithubAsset:url')
        return self.url

    def tag(self):
        logging.debug('GithubAsset:tag')
        return self.tag

    def release_date(self):
        logging.debug('GithubAsset:release_date')
        return self.release_date
