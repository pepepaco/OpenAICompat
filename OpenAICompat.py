import base64
import json
import requests
import io
import torch
import numpy as np
import time
from PIL import Image

class OpenAICompat:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "system_prompt": ("STRING", {"default": "", "multiline": True}),
                "openai_url": ("STRING", {"default": "http://localhost:8080/v1/chat/completions"}),
                "api_key": ("STRING", {"default": "lm-studio", "salted": True}),
                "model": ("STRING", {"default": "gpt-4o-mini"}),
                "resize_percent": ("FLOAT", {"default": 30.0, "min": 1.0, "max": 100.0}),
                "custom_properties": ("STRING", {"default": '{"temperature": 0.3}', "multiline": True}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**31-1}),
                "bypass": (["disable", "enable"], {"default": "disable"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("ENHANCED_PROMPT",)
    FUNCTION = "process"
    CATEGORY = "OpenAICompat"

    def process(self, image, prompt, system_prompt, openai_url, api_key, model, resize_percent=30.0, custom_properties="{}", seed=0, bypass="disable"):

        if bypass == "enable":
            return (prompt,)

        # 1. Image Processing
        i = 255. * image[0].cpu().numpy()
        img_obj = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

        if int(resize_percent) != 100:
            new_w = int(img_obj.width * resize_percent / 100)
            new_h = int(img_obj.height * resize_percent / 100)
            img_obj = img_obj.resize((new_w, new_h), Image.LANCZOS)

        buffered = io.BytesIO()
        img_obj.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        kb = len(img_bytes) / 1024.0
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        # 2. Message Configuration
        messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
        messages.append({"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": prompt}
        ]})

        # 3. Request and Console Stats
        try:
            extra_props = json.loads(custom_properties) if custom_properties.strip() else {}
            payload = {"model": model, "messages": messages, "stream": False, "seed": seed, **extra_props}

            start_time = time.time()
            resp = requests.post(openai_url, headers={"Authorization": f"Bearer {api_key}"}, json=payload, timeout=120)
            duration = time.time() - start_time

            if resp.status_code == 200:
                result_json = resp.json()
                result = result_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                tokens = result_json.get('usage', {}).get('total_tokens', 'N/A')

                print(f"\n[OpenAI-Stats] Time: {duration:.2f}s | Payload: {kb:.2f} Kb | Tokens: {tokens}")

                return (result,)
            else:
                print(f"\n[OpenAI-Error] Status: {resp.status_code} | Msg: {resp.text}")
        except Exception as e:
            print(f"\n[OpenAI-PythonError] {str(e)}")

        return (prompt,)

NODE_CLASS_MAPPINGS = {"OpenAICompat": OpenAICompat}
NODE_DISPLAY_NAME_MAPPINGS = {"OpenAICompat": "OpenAICompat"}