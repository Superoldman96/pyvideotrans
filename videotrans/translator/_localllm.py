# -*- coding: utf-8 -*-
import re
from typing import Union, List

import httpx,requests
from openai import OpenAI, APIConnectionError

from videotrans.configure import config
from videotrans.translator._base import BaseTrans
from videotrans.util import tools


class LocalLLM(BaseTrans):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trans_thread=int(config.settings.get('aitrans_thread',500))
        self.api_url = config.params['localllm_api']
        self.prompt = tools.get_prompt(ainame='localllm',is_srt=self.is_srt).replace('{lang}', self.target_language_name)
        self._check_proxy()
        if not self.api_url:
            raise Exception('Input your API URL')
        self.model_name=config.params["localllm_model"]

        
    def _check_proxy(self):
        if re.search('localhost', self.api_url) or re.match(r'^https?://(\d+\.){3}\d+(:\d+)?', self.api_url):
            return
        try:
            c=httpx.Client(proxies=None)
            c.get(self.api_url)
        except Exception as e:
            pro = self._set_proxy(type='set')
            if pro:
                self.proxies = {"https://": pro, "http://": pro}
    def _item_task(self, data: Union[List[str], str]) -> str:
        model = OpenAI(api_key=config.params['localllm_key'], base_url=self.api_url,
                       http_client=httpx.Client(proxies=self.proxies))
        message = [
            {'role': 'system',
             'content': "You are a translation assistant specializing in converting SRT subtitle content from one language to another while maintaining the original format and structure." if config.defaulelang != 'zh' else '您是一名翻译助理，专门负责将 SRT 字幕内容从一种语言转换为另一种语言，同时保持原始格式和结构。'},
            {'role': 'user',
             'content': self.prompt.replace('[TEXT]',"\n".join([i.strip() for i in data]) if isinstance(data, list) else data)},
        ]
        config.logger.info(f"\n[localllm]发送请求数据:{message=}")
        try:
            response = model.chat.completions.create(
                model=config.params['localllm_model'],
                messages=message
            )
        except APIConnectionError:
            raise requests.ConnectionError('connection error')
        config.logger.info(f'[localllm]响应:{response=}')

        if isinstance(response, str):
            raise Exception(f'{response=}')

        if response.choices:
            result = response.choices[0].message.content.strip()
        elif response.data and response.data['choices']:
            result = response.data['choices'][0]['message']['content'].strip()
        else:
            raise Exception(f'[localllm]请求失败:{response=}')

        match = re.search(r'<TRANSLATE_TEXT>(.*?)</TRANSLATE_TEXT>', result,re.S)
        if match:
            return match.group(1)
        raise Exception('No content')

