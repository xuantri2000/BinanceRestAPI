import os
import time
import requests
import telebot
import threading
import schedule
from datetime import datetime, timedelta
from pytz import timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Cấu hình bot Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = 'https://api.binance.com/api/v3'

# Tạo bot Telegram
bot = telebot.TeleBot(BOT_TOKEN)
CHECKLIST_FILE = 'checklist.txt'
USER_CHAT_ID = None  # Biến toàn cục để lưu chat_id

def read_coin_list():
	if not os.path.exists(CHECKLIST_FILE):
		return []
	with open(CHECKLIST_FILE, 'r') as f:
		return [coin.strip().upper() for coin in f.readlines()]

def write_coin_list(coins):
	with open(CHECKLIST_FILE, 'w') as f:
		for coin in coins:
			f.write(f"{coin.upper()}\n")

# Thêm handler để lưu chat_id khi start bot
@bot.message_handler(commands=['start'])
def start_handler(message):
	global USER_CHAT_ID
	USER_CHAT_ID = message.chat.id
	bot.reply_to(message, "Bot đã được khởi động. Bạn có thể bắt đầu sử dụng các lệnh.")

@bot.message_handler(commands=['add'])
def add_coins(message):
	try:
		# Split by comma and handle multiple coins in one command
		coins_to_add = [coin.strip().upper() for coin in message.text.split('/add')[1].replace(',', '\n').split('\n') if coin.strip()]
		current_coins = read_coin_list()
		
		# Track newly added coins
		newly_added = []
		for coin in coins_to_add:
			if coin not in current_coins:
				current_coins.append(coin)
				newly_added.append(coin)
		
		# Write updated list
		write_coin_list(current_coins)
		
		if newly_added:
			response = "Đã thêm các coin sau:\n" + "\n".join(newly_added)
		else:
			response = "Không có coin mới được thêm. Tất cả các coin đã tồn tại."
		
		bot.reply_to(message, response)
	except Exception as e:
		bot.reply_to(message, f"Lỗi: {str(e)}")

@bot.message_handler(commands=['remove'])
def remove_coins(message):
	try:
		# Split by comma and handle multiple coins in one command
		coins_to_remove = [coin.strip().upper() for coin in message.text.split('/remove')[1].replace(',', '\n').split('\n') if coin.strip()]
		current_coins = read_coin_list()
		current_coins = [coin for coin in current_coins if coin not in coins_to_remove]
		write_coin_list(current_coins)
		response = "Đã xóa các coin sau:\n" + "\n".join(coins_to_remove)
		bot.reply_to(message, response)
	except Exception as e:
		bot.reply_to(message, f"Lỗi: {str(e)}")

@bot.message_handler(commands=['list'])
def list_coins(message):
	coins = read_coin_list()
	if coins:
		response = "Danh sách coin hiện tại:\n" + "\n".join(coins)
	else:
		response = "Danh sách coin trống."
	bot.reply_to(message, response)

def check_coin_limits():
	global USER_CHAT_ID
	if USER_CHAT_ID is None:
		return  # Exit if no chat_id

	coins = read_coin_list()
	utc_tz = timezone('UTC')
	current_time_utc = datetime.now(utc_tz)
	chunk_start = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0)
	chunk_end = current_time_utc
	index = 1

	alert_messages = []  # List to store messages

	for symbol in coins:
		try:
			params = {
				'symbol': symbol,
				'interval': '5m',
				'startTime': int(chunk_start.timestamp() * 1000),
				'endTime': int(chunk_end.timestamp() * 1000),
				'limit': 500
			}
			response = requests.get(f"{BASE_URL}/klines", params=params)
			data = response.json()

			if response.status_code != 200:
				print(f"HTTP error when checking {symbol}: {response.status_code}")
				continue

			if not data or not isinstance(data, list):
				print(f"Invalid or empty data for {symbol}: {data}")
				continue

			try:
				# Process data to get 4 records with lowest and highest low prices
				formatted_data = []
				for kline in data:
					# Convert timestamp to UTC time
					open_time = datetime.fromtimestamp(int(float(kline[0])) / 1000, tz=utc_tz)
					formatted_time = open_time.strftime('%d.%m.%y - %H:%M')
					low_price = float(kline[3])  # Lowest price
					formatted_kline = [formatted_time, low_price]
					formatted_data.append(formatted_kline)

				# Sort by low price and get 2 lowest and 2 highest
				formatted_data.sort(key=lambda x: x[1])
				

				lowest_2 = formatted_data[:2]
				highest_2 = formatted_data[-2:]

				# Create message for each record
				alert_message = f"{index}) {symbol}:\n"
				index += 1
				
				# Combine and sort by time
				combined_records = sorted(lowest_2 + highest_2, key=lambda x: datetime.strptime(x[0], '%d.%m.%y - %H:%M'), reverse=True)
				
				for i, (time, low) in enumerate(combined_records):
					# Add ellipsis in the middle if it's the second set of records
					if i == 2:
						alert_message += "  ...\n"
					alert_message += f"  {time} : {low:.8f}\n"
				
				alert_message += "------------------------------"

				alert_messages.append(alert_message)  # Add message to list

			except ValueError:
				print(f"Error converting data to float for {symbol}: {data}")
				continue

		except Exception as e:
			print(f"Error checking {symbol}: {e}")

	# Send all messages after checking is complete
	if alert_messages:
		full_alert = f"****** Automatic Telegram Bot Message ******\n"
		full_alert += f"Monitoring data at {datetime.now(utc_tz).strftime('%H:%M - %d.%m.%y')} UTC:\n\n"
		full_alert += "\n".join(alert_messages)
		bot.send_message(chat_id=USER_CHAT_ID, text=full_alert)

def run_schedule():
	schedule.every(10).seconds.do(check_coin_limits)
	while True:
		schedule.run_pending()
		time.sleep(1)

def start_telegram_bot():
	bot_thread = threading.Thread(target=bot.polling)
	bot_thread.start()

def start_schedule():
	schedule_thread = threading.Thread(target=run_schedule)
	schedule_thread.start()

if __name__ == '__main__':
	start_telegram_bot()
	start_schedule()