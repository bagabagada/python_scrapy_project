import scrapy
from scrapy_redis.spiders import RedisSpider
from bs4 import BeautifulSoup
from pymongo import MongoClient
import redis
from ..items import MusicListItem


class MusicListSpider(RedisSpider):
    name = 'music_list_spider'
    redis_key = 'list_url_queue'  # 从 Redis 获取起始 URL
    collection_name = 'music_list'

    def __init__(self, *args, **kwargs):
        super(MusicListSpider, self).__init__(*args, **kwargs)

        # 连接到 MongoDB
        self.mongo_client = MongoClient('localhost', 27017, username='root', password='123456')
        self.db = self.mongo_client['music_datas']
        self.collection = self.db[self.collection_name]

        # 连接到 Redis
        self.r = redis.StrictRedis(host='localhost', port=6379, db=0)

    def start_requests(self):
        """生成带有不同 offset 的 URL 并推送到 Redis"""
        for offset in range(0, 2000, 35):  # 从 0 到 2000，步长为 35
            url = f'https://music.163.com/discover/playlist/?cat=欧美&order=hot&limit=35&offset={offset}'
            self.r.lpush(self.redis_key, url)  # 将生成的 URL 推送到 Redis
        while True:
            url = self.r.rpop(self.redis_key)
            if not url:
                break
            yield scrapy.Request(url=url.decode('utf-8'), callback=self.parse)

    def parse(self, response):
        """解析歌单索引页"""
        soup = BeautifulSoup(response.text, 'html.parser')

        # 获取包含歌单详情页网址的标签
        ids = soup.select('.dec a')
        lis = soup.select('#m-pl-container li')

        for j in range(len(lis)):
            url = ids[j]['href']  # 详情页地址
            title = ids[j]['title'].replace(',', '，')  # 歌单标题
            play = lis[j].select('.nb')[0].get_text()  # 歌单播放量
            user = lis[j].select('p')[1].select('a')[0].get_text()  # 歌单贡献者名字

            # 创建并保存 MusicListItem 实例
            item = MusicListItem(url=url, title=title, play=play, user=user)
            self.collection.insert_one(item)

            # 将详情页 URL 推送到 Redis 队列 detail_url_queue
            self.r.lpush('detail_url_queue', f"https://music.163.com{url}")

            yield item