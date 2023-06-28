from mythic.logger import logger

import base64
import requests
from ratelimit import limits, sleep_and_retry


class WowApi:
    def __init__(self, region, api_id, api_secret):
        self.region = region
        self.api_id = api_id
        self.api_secret = api_secret
        self.access_token = self.get_token()
        logger.info(f'token = {self.access_token}')

    @sleep_and_retry
    @limits(calls=600, period=1)
    def get_token(self, retry=10):
        url = f"https://{self.region}.battle.net/oauth/token"
        api_id = self.api_id
        api_secret = self.api_secret
        auth = base64.b64encode(
            (api_id + ':' + api_secret).encode()).decode('utf-8')

        headers = {
            'Authorization': 'Basic ' + auth,
            'Content-Type': "application/x-www-form-urlencoded"
        }

        res = requests.post(url, headers=headers, data={
                            'grant_type': 'client_credentials'})
        if res.status_code == 200:
            res_obj = res.json()
            if 'access_token' in res_obj:
                return res_obj['access_token']
        
        if retry >= 0:
            return self.get_token(retry - 1)
        
        return ''

    def locale(self):
        if self.region == "us":
            return "en_US"
        elif self.region == "eu":
            return "en_GB"
        elif self.region == "kr":
            return "ko_KR"
        elif self.region == "tw":
            return "zh_TW"
        return ""

    @sleep_and_retry
    @limits(calls=600, period=1)
    def bn_request(self, url, token=False, namespace=None, retry=10):
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

        # logger.info(url)
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                return res.json()
            elif res.status_code == 401:
                logger.info('invalid token')
                if retry >= 0:
                    self.access_token = self.get_token()
                    return self.bn_request(url, token=token, namespace=namespace, retry=retry-1)
                else:
                    return res.status_code
            else:
                return res.status_code
        except requests.exceptions.Timeout:
            logger.info(f'timeout! retry={retry}')
            if retry > 0:
                return self.bn_request(url, token=token, namespace=namespace, retry=retry-1)
            return None
