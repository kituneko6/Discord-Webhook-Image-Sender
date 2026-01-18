import requests
import flet as ft
from io import BytesIO
from PIL import Image as PILImage, ExifTags
import base64
import pyperclip
import os


# ---- 設定 ----
#BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBHOOK_URL_FILE = os.path.join("webhook_url.txt")
MAX_SIZE = 2048


# ---- Webhook URL 読み込み ----
def load_webhook_url():
    if not os.path.exists(WEBHOOK_URL_FILE):
        raise FileNotFoundError(f"{WEBHOOK_URL_FILE} が見つかりません。")
    with open(WEBHOOK_URL_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


# ---- Exif補正 ----
def fix_exif(image: PILImage.Image):
    try:
        exif = image._getexif()
        if exif is not None:
            ori_key = next(key for key, val in ExifTags.TAGS.items() if val == "Orientation")
            ori = exif.get(ori_key)
            if ori == 2:
                image = image.transpose(PILImage.FLIP_LEFT_RIGHT)
            elif ori == 3:
                image = image.rotate(180, expand=True)
            elif ori == 4:
                image = image.transpose(PILImage.FLIP_TOP_BOTTOM)
            elif ori == 5:
                image = image.transpose(PILImage.FLIP_TOP_BOTTOM).rotate(-90, expand=True)
            elif ori == 6:
                image = image.rotate(-90, expand=True)
            elif ori == 7:
                image = image.transpose(PILImage.FLIP_LEFT_RIGHT).rotate(-90, expand=True)
            elif ori == 8:
                image = image.rotate(90, expand=True)
    except Exception:
        pass
    return image


# ---- 比率を保ったまま最大2048pxに縮小 ----
def resize_image(image: PILImage.Image, max_size=MAX_SIZE):
    image = fix_exif(image)
    original_size = image.size
    if image.width > max_size or image.height > max_size:
        image.thumbnail((max_size, max_size))
        print(f"リサイズ: {original_size} → {image.size}")
    else:
        print(f"リサイズ不要: {original_size}")
    return image


# ---- Webhookに画像を送信 ----
def send_to_discord(file_path: str, webhook_url: str):
    with open(file_path, "rb") as f:
        response = requests.post(
            webhook_url,
            files={"file": (os.path.basename(file_path), f, "image/png")},
        )
    if response.status_code == 200 or response.status_code == 204:
        data = response.json()
        if "attachments" in data and data["attachments"]:
            return data["attachments"][0]["url"]
        else:
            raise Exception("送信成功しましたが、画像URLを取得できませんでした。")
    else:
        raise Exception(f"送信失敗: {response.status_code} {response.text}")


# ---- GUI本体 ----
def main(page: ft.Page):
    page.title = "Discord Webhook Image Sender"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.padding = 20

    url_field = ft.TextField(label="画像URLまたはローカルパス", width=500)
    status_combined = ft.Text("", text_align="left", selectable=True)

    # ✅ v0.80ではsrc必須。空文字で初期化しておく
    EMPTY_IMAGE_DATAURI = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMB/6X8oAAAAABJRU5ErkJggg=="
    )

    image_preview = ft.Image(src=EMPTY_IMAGE_DATAURI, width=400, fit="contain")

    webhook_url = load_webhook_url()

    def paste_clipboard(e):
        try:
            clip = pyperclip.paste()
            url_field.value = clip
            page.update()
        except Exception as ex:
            status_combined.value = f"Clipboard Error: {ex}"
            page.update()

    def process_image(e):
        try:
            src = url_field.value.strip()
            if src.startswith('"') and src.endswith('"'):
                src = src[1:-1]

            if src.startswith("http"):
                response = requests.get(src)
                response.raise_for_status()
                image = PILImage.open(BytesIO(response.content))
            else:
                image = PILImage.open(src)

            image = resize_image(image)
            image.save("output.png")

            # プレビュー用サムネイルを作成して表示
            thumb = image.copy()
            img_bytes = BytesIO()
            thumb.save(img_bytes, format="PNG")
            img_base64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

            # ✅ v0.80以降の正しい方法
            image_preview.src = "data:image/png;base64," + img_base64
            image_preview.update()

            status_combined.value = f"画像準備完了: {image.size}"
            page.update()

            # Discord送信
            image_url = send_to_discord("output.png", webhook_url)
            pyperclip.copy(image_url)
            status_combined.value = f"✅ 送信完了！URLをクリップボードにコピーしました\n{image_url}"
            page.update()

        except Exception as ex:
            status_combined.value = f"Error: {ex}"
            page.update()

    center_content = ft.Column(
        [
            ft.Row([url_field, ft.Button("📋貼り付け", on_click=paste_clipboard)], alignment="center"),
            ft.Button("画像変換＆送信", on_click=process_image),
            image_preview,
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    bottom_status = ft.Container(
        content=status_combined,
        alignment=ft.alignment.Alignment(-1, 1),
        padding=ft.padding.only(left=200, bottom=10),
    )

    page.add(
        ft.Column(
            [center_content, bottom_status],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            expand=True,
        )
    )


# ✅ Flet 0.70以降は run() を使用
if __name__ == "__main__":
    ft.run(main)
