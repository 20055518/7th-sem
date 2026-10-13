import base64
import io
import secrets

import qrcode


def generate_qr_token() -> str:
    return secrets.token_urlsafe(32)


def generate_qr_image_data(token: str) -> str:
    qr_image = qrcode.make(token)
    image_buffer = io.BytesIO()
    qr_image.save(image_buffer, "PNG")
    encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded_image}"
