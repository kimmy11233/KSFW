import requests
import base64
from src.IConnectors import IImageConnector

class SDUIConnector(IImageConnector):
    def __init__(self, base_url="http://localhost:7860"):
        self.base_url = base_url.rstrip('/')


    async def txt2img(self, prompt, negative_prompt, steps=28, path="./tmp/temp.png"):
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "sampler_name": "Euler a",
            "cfg_scale": 7
        }

        response = requests.post(url=f'{self.base_url}/sdapi/v1/txt2img', json=payload)
        response.raise_for_status()
        r = response.json()
        with open(path, 'wb') as f:
            f.write(base64.b64decode(r['images'][0]))
        
        return path


async def test_sd_ui_connector():
    await SDUIConnector().txt2img("masterpiece, best quality, masterpiece, asuka langley sitting cross legged on a chair", "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts,signature, watermark, username, blurry, artist name", 28)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_sd_ui_connector())