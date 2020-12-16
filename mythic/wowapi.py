from mythic.logger import logger

import base64
import requests

class WowApi:
    def __init__(self, region, api_id, api_secret):
        self.region = region
        self.api_id = api_id
        self.api_secret = api_secret
        self.access_token = self.get_token()
        logger.info(f'token = {self.access_token}')

    def get_token(self):
        url = f"https://{self.region}.battle.net/oauth/token"
        api_id = self.api_id
        api_secret = self.api_secret
        auth = base64.b64encode((api_id + ':' + api_secret).encode()).decode('utf-8')

        headers = {
            'Authorization': 'Basic ' + auth,
            'Content-Type': "application/x-www-form-urlencoded"
        }
        
        res = requests.post(url, headers=headers, data={'grant_type': 'client_credentials'})
        if res.status_code == 200:
            res_obj = res.json()
            if 'access_token' in res_obj:
                return res_obj['access_token']
        return None

    def locale(self):
        if self.region == "us":
            return "en_US"
        elif self.region == "eu":
            return "en_GB"
        elif self.region ==  "kr":
            return "ko_KR"
        elif self.region ==  "tw":
            return "zh_TW"
        return ""

    def bn_request(self, url, token=False, namespace=None, retry=True):
        if not url.startswith('http'):
            url = f"https://{self.region}.api.blizzard.com:443" + url

        if token:
            url += '&' if url.find('?') >= 0 else '?'
            url += "access_token=" + self.access_token
        if namespace != None:
            url += '&' if url.find('?') >= 0 else '?'
            url += f"region={self.region}"
            url += f"&namespace={namespace}-{self.region}"
            url += f"&locale={self.locale()}"

        logger.info(url)
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 401:
            logger.info('invalid token')
            if retry:
                self.access_token = self.get_token()
                return self.bn_request(url, token=token, namespace=namespace, retry=False)
            else:
                return None
        else:
            return None
