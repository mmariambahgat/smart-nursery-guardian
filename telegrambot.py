import telebot
TOKEN = "8655569324:AAHeBKNMEz-yj_zkYCOozKrDOX1cG9xXgA4"
bot = telebot.TeleBot(TOKEN)
CHAT_ID = "1647562731"

def gas_alert():
    bot.send_message(
        chat_id=CHAT_ID,
        text="GAS/SMOKE ALERT!!!\n GAS OR SMOKE HAS BEEN DETECTED"
    )

