import io
from typing import Any, List

from core.file.enums import FileType
from core.file.file_manager import download
from core.model_manager import ModelManager
from core.model_runtime.entities.model_entities import ModelType
from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolInvokeMessage, ToolParameter, ToolParameterOption
from core.tools.tool.builtin_tool import BuiltinTool
from services.model_provider_service import ModelProviderService

import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

class IFlytek(object):
    def __init__(self, app_id, api_key, api_secret):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret 
        self.audio_stream = b''
        self.format = 'lame'#.mp3
        # self.format = 'raw'#.pcm
        self.text = ""            
        self.business_args = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo":1,"vad_eos":10000}

    def get_audio_text(self, audio_binary, format='lame'):
        try:
            if audio_binary:
                self.audio_stream = audio_binary
                self.format = format
                websocket.enableTrace(False)
                ws_url = self.create_url()
                print(f"Attempting to connect with URL: {ws_url}")  # 打印生成的URL用于调试
                ws = websocket.WebSocketApp(ws_url, on_message=self.on_message, on_error=self.on_error, on_close=self.on_close)
                ws.on_open = self.on_open
                ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        except Exception as e:
            logger.error(f"An exception occurred: {e}")
        finally:
            return self.text

    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'

        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"

        signature_sha = hmac.new(self.api_secret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.api_key, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        url = url + '?' + urlencode(v)
        return url

    def on_message(self, ws, message):
        try:
            code = json.loads(message)["code"]
            sid = json.loads(message)["sid"]
            if code != 0:
                errMsg = json.loads(message)["message"]
                print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
            else:
                data = json.loads(message)["data"]["result"]["ws"]
                # print(json.loads(message))
                result = ""
                for i in data:
                    for w in i["cw"]:
                        result += w["w"]
                # print("sid:%s call success!,data is:%s" % (sid, json.dumps(data, ensure_ascii=False)))
                self.text += result
        except Exception as e:
            logger.warning(f"receive msg,but parse exception: {e}")

    def on_error(self, ws, error):
        logger.error("error:", error)

    def on_close(self, ws,a,b):
        print("### closed ###", a, b)

    def on_open(self, ws):      
        def run(*args):
            frameSize = 8000  # 每一帧的音频大小
            intervel = 0.04  # 发送音频间隔(单位:s)
            status = STATUS_FIRST_FRAME  # 音频的状态信息，标识音频是第一帧，还是中间帧、最后一帧     
            while True:
                buf = self.audio_stream.read(frameSize)

                if not buf:
                    status = STATUS_LAST_FRAME

                if status == STATUS_FIRST_FRAME:
                    d = {"common": {"app_id": self.app_id},
                        "business": self.business_args,
                        "data": {"status": 0, "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(buf), 'utf-8'),
                                "encoding": self.format}}
                    d = json.dumps(d)
                    ws.send(d)
                    status = STATUS_CONTINUE_FRAME
                elif status == STATUS_CONTINUE_FRAME:
                    d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(buf), 'utf-8'),
                                "encoding": self.format}}
                    ws.send(json.dumps(d))
                elif status == STATUS_LAST_FRAME:
                    d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(buf), 'utf-8'),
                                "encoding": self.format}}
                    ws.send(json.dumps(d))
                    time.sleep(1)
                    break
                time.sleep(intervel)
            ws.close()
        thread.start_new_thread(run, ())

class AndleohtASRTool(BuiltinTool):    
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> list[ToolInvokeMessage]:
        try:
            file = tool_parameters.get("audio_file")
            if file.type != FileType.AUDIO:
                return [self.create_text_message("not a valid audio file")]  
            audio_binary = io.BytesIO(download(file))
            audio_binary.name = "temp.mp3"
        
            app_id = self.runtime.credentials["xfyun_app_id"]
            api_key = self.runtime.credentials["xfyun_api_key"]
            api_secret = self.runtime.credentials["xfyun_api_secret"] 
            asr_iflytek = IFlytek(app_id, api_key, api_secret)
            text = asr_iflytek.get_audio_text(audio_binary)
        except Exception as e:
            logger.warning(f"An exception occurred: {e}")
        return [self.create_text_message(text)]

    # def get_runtime_parameters(self) -> List[ToolParameter]:
    #     return [
    #         ToolParameter(
    #             name="audio_file",
    #             label=I18nObject(en_US="Audio File", zh_Hans="音频文件"),
    #             type=ToolParameter.ToolParameterType.SELECT,
    #             required=True,
    #             form=ToolParameter.ToolParameterForm.FORM,
    #             options=[
    #                 ToolParameterOption(
    #                     value="audio/mp3",
    #                     label=I18nObject(en_US="MP3", zh_Hans="MP3")
    #                 ),
    #                 ToolParameterOption(
    #                     value="audio/wav",
    #                     label=I18nObject(en_US="WAV", zh_Hans="WAV")
    #                 )
    #             ]
    #         )
    #     ]
    
     