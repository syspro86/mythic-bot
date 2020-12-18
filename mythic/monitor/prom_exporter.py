from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot
from datetime import datetime
import time
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

class MythicExporter(BaseBot):
    def __init__(self):
        super().__init__()

        self.end_timestamp = 0

        self.init_api()

    def init_api(self):
        periods = self.api.bn_request("/data/wow/mythic-keystone/period/index", token=True, namespace="dynamic")

        self.current_period = periods['current_period']['id']
        period_detail = self.api.bn_request(f"/data/wow/mythic-keystone/period/{self.current_period}", token=True, namespace="dynamic")
        self.end_timestamp = int(period_detail['end_timestamp'])

    def collect(self):
        metrics = []
        try:
            now_ts = int(datetime.now().timestamp() * 1000)
            if self.end_timestamp < now_ts:
                self.need_init = True
                self.init_api()
                # 현재 시간에 맞는 period가 없음.
                if self.end_timestamp < now_ts:
                    return

            cnt = self.db.aggregate('records', [
                { '$match': { 'period': self.current_period } },
                { '$count': 'count' },
            ])
            
            m = GaugeMetricFamily('period_record_count', 'period record count', labels=["rec_count"])
            m.add_metric(['cnt'], cnt[0]['count'])
            metrics.append(m)
            
        except Exception as e:
            self.print_error(e)

        return metrics

    def start(self):
        REGISTRY.register(self)
        start_http_server(8000)
        while True:
            time.sleep(60)

if __name__ == '__main__':
    MythicExporter().start()
