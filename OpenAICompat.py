import base64
import json
import requests
import hashlib
import io
import torch
import numpy as np
import time  # Nuevo para medir el tiempo
from PIL import Image

class OpenAICompat:
    _last_prompt = None
    _last_response = None
    _last_img_hash = None
    _last_img_b64 = None
    _last_img_info = None

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
            }
        }

    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("ENHANCED_PROMPT", "LOG",)
    FUNCTION = "process"
    CATEGORY = "OpenAICompat"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def process(self, image, prompt, system_prompt, openai_url, api_key, model, resize_percent=30.0, custom_properties="{}", seed=0):
        logs = []

        # 1. Procesamiento de Imagen
        img_content_hash = hashlib.sha256(image.cpu().numpy().tobytes()).hexdigest()
        img_process_key = f"{img_content_hash}||{resize_percent}"

        if img_process_key == self._last_img_hash and self._last_img_b64 is not None:
            w, h, kb = self._last_img_info
            logs.append(f"Image: CACHE HIT ({w}x{h}, {kb:.2f} Kb)")
            current_img_b64 = self._last_img_b64
        else:
            i = 255. * image[0].cpu().numpy()
            img_obj = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            if int(resize_percent) != 100:
                new_w = int(img_obj.width * resize_percent / 100)
                new_h = int(img_obj.height * resize_percent / 100)
                img_obj = img_obj.resize((new_w, new_h), Image.LANCZOS)

            w, h = img_obj.size
            buffered = io.BytesIO()
            img_obj.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            kb = len(img_bytes) / 1024.0

            current_img_b64 = base64.b64encode(img_bytes).decode("utf-8").strip()
            self._last_img_hash = img_process_key
            self._last_img_b64 = current_img_b64
            self._last_img_info = (w, h, kb)
            logs.append(f"Image: CACHE MISS ({w}x{h}, {kb:.2f} Kb)")

        # 2. Verificación de Caché Global
        combined_key = f"{prompt}{system_prompt}{model}{custom_properties}{seed}{img_process_key}"

        if combined_key == self._last_prompt:
            logs.append("Global Prompt: CACHE HIT")
            return (self._last_response, "\n".join(logs))

        # 3. Llamada a la API con medición de tiempo
        logs.append("Global Prompt: CACHE MISS. Calling API...")
        messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
        messages.append({"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{current_img_b64}"}},
            {"type": "text", "text": prompt}
        ]})

        try:
            extra_props = json.loads(custom_properties) if custom_properties.strip() else {}
            payload = {"model": model, "messages": messages, "stream": False, "seed": seed, **extra_props}

            # --- MEDICIÓN DE TIEMPO ---
            start_time = time.time()
            resp = requests.post(openai_url, headers={"Authorization": f"Bearer {api_key}"}, json=payload, timeout=120)
            end_time = time.time()
            duration = end_time - start_time
            # --------------------------

            if resp.status_code == 200:
                result_json = resp.json()
                result = result_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                self._last_prompt = combined_key
                self._last_response = result
                tokens = result_json.get('usage', {}).get('total_tokens', 'N/A')
                logs.append(f"API Success. Time: {duration:.2f}s, Tokens: {tokens}")
                return (result, "\n".join(logs))
            else:
                logs.append(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            logs.append(f"Error: {str(e)}")

        return (prompt, "\n".join(logs))

NODE_CLASS_MAPPINGS = {"OpenAICompat": OpenAICompat}
NODE_DISPLAY_NAME_MAPPINGS = {"OpenAICompat": "OpenAICompat"}