import asyncio
import datetime
import os
import io
from time import sleep

def save_receipt(driver, player_ID, recharge_redeem_amount, recharge_bot, receipt_group_ids, receipt_topic_id):
    sleep(1.5)  # Ensure the UI is fully loaded before taking screenshot
    tele_url = f"https://t.me/c/{str(receipt_group_ids)[4:]}/"
    # Generate unique file name
    now = datetime.datetime.now()
    name = f"{now.month}.{now.day}.{now.hour}.{now.minute}.{now.second}"
    filename = f"{player_ID}_{recharge_redeem_amount}_{name}.png"

    # Capture screenshot in memory (not saved to disk)
    screenshot_data = driver.get_screenshot_as_png()
    screenshot_stream = io.BytesIO(screenshot_data)
    screenshot_stream.name = filename  # Optional: gives it a name
    screenshot_stream.seek(0)

    message_url_link = ""
    try:
        # Send screenshot as photo
        receipt = asyncio.run(recharge_bot.send_photo(
            chat_id=int(receipt_group_ids),
            photo=screenshot_stream,
            reply_to_message_id=receipt_topic_id
        ))
        receipt_id = receipt.message_id
        message_url_link = f"{tele_url}{receipt_topic_id}/{receipt_id}"
        print("Sent photo to group:", message_url_link)

    except Exception as e:
        print("Sending image failed:", e)

    return message_url_link
