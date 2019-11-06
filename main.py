import os

import requests
import slackweb
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, ImageMessage, StickerMessage

app = Flask(__name__)

# 認証情報の取得
CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
WEB_HOOK_LINKS = os.environ["SLACK_WEB_HOOKS_URL"]
BOT_OAUTH = os.environ["SLACK_BOT_OAUTH"]
POST_CHANEL_ID = os.environ["SLACK_POST_CHANEL_ID"]

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle web hook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


def get_event_info(event):
    """
    トーク情報の取得
    :param event: LINE メッセージイベント
    :return: ユーザID, ユーザ表示名, 送信元トークルームの種別, ルームID
    :rtype: str, str, str, str
    """

    # LINEユーザー名の取得
    user_id = event.source.user_id
    try:
        user_name = line_bot_api.get_profile(user_id).display_name
    except LineBotApiError as e:
        user_name = "Unknown"

    # トーク情報の取得
    if event.source.type == "user":
        msg_type = "個別"
        room_id = None
        return user_id, user_name, msg_type, room_id

    if event.source.type == "group":
        msg_type = "グループ"
        room_id = event.source.group_id
        return user_id, user_name, msg_type, room_id

    if event.source.type == "room":
        msg_type = "複数トーク"
        room_id = event.source.room_id
        return user_id, user_name, msg_type, room_id


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """
    Text Message の処理
    """

    slack_info = slackweb.Slack(url=WEB_HOOK_LINKS)

    # トーク情報の取得
    user_id, user_name, msg_type, room_id = get_event_info(event)

    # slack側に投稿するメッセージの加工
    send_msg = "[bot-line] {user_name}さん\n".format(user_name=user_name) \
               + "{msg}\n".format(msg=event.message.text) \
               + "---\n" \
               + "送信元: {msg_type} ( {room_id} )\n".format(msg_type=msg_type, room_id=room_id) \
               + "送信者: {user_name} ( {user_id} )".format(user_name=user_name, user_id=user_id)

    # メッセージの送信
    slack_info.notify(text=send_msg)


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """
    Image Message の処理
    """

    # トーク情報の取得
    user_id, user_name, msg_type, room_id = get_event_info(event)

    # LINEで送信された画像の取得
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    img = message_content.content

    # slack側に投稿するメッセージの加工
    send_msg = "[bot-line] {user_name}さんが画像を送信しました．\n".format(user_name=user_name) \
               + "---\n" \
               + "送信元: {msg_type} ( {room_id} )\n".format(msg_type=msg_type, room_id=room_id) \
               + "送信者: {user_name} ( {user_id} )".format(user_name=user_name, user_id=user_id)

    file_name = "send_image_{message_id}".format(message_id=message_id)

    # 画像送信
    files = {'file': img}
    param = {
        'token': BOT_OAUTH,
        'channels': POST_CHANEL_ID,
        'filename': file_name,
        'initial_comment': send_msg,
        'title': file_name
    }
    response = requests.post(url="https://slack.com/api/files.upload", params=param, files=files)


@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    """
    Sticker Message の処理
    """

    slack_info = slackweb.Slack(url=WEB_HOOK_LINKS)

    # トーク情報の取得
    user_id, user_name, msg_type, room_id = get_event_info(event)

    # LINEで送信されたスタンプ情報の取得
    package_id = event.message.package_id
    sticker_id = event.message.sticker_id

    # slack側に投稿するメッセージの加工
    send_msg = "[bot-line] {user_name}さんがスタンプを送信しました．\n".format(user_name=user_name) \
               + "package_id: {package_id}\n".format(package_id=package_id) \
               + "sticker_id: {sticker_id}\n".format(sticker_id=sticker_id) \
               + "---\n" \
               + "送信元: {msg_type} ( {room_id} )\n".format(msg_type=msg_type, room_id=room_id) \
               + "送信者: {user_name} ( {user_id} )".format(user_name=user_name, user_id=user_id)

    # メッセージの送信
    slack_info.notify(text=send_msg)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
