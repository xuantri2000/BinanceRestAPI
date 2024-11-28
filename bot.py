import os
import time
import requests
import telebot
import json
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
PREVIOUS_RATIO_FILE = 'previous_ratios.json'
USER_CHAT_ID = None  # Biến toàn cục để lưu chat_id

def load_previous_ratios():
	if os.path.exists(PREVIOUS_RATIO_FILE):
		with open(PREVIOUS_RATIO_FILE, 'r') as f:
			try:
				return json.load(f)
			except json.JSONDecodeError:
				return {}
	return {}

def save_previous_ratios(ratios):
	with open(PREVIOUS_RATIO_FILE, 'w') as f:
		json.dump(ratios, f)

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
	bot.reply_to(message, "Bắt đầu theo dõi coin theo danh sách.")

	time.sleep(1)
	check_coin_limits()

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

@bot.message_handler(commands=['help'])
def help_command(message):
	help_text = """
📋 Danh sách các lệnh hỗ trợ:

/start - Bắt đầu theo dõi coin và lưu chat ID
/help - Hiển thị danh sách các lệnh hỗ trợ

Quản lý Danh Sách Coin:
/add [coin1, coin2, ...] - Thêm coin vào danh sách theo dõi
	Ví dụ: /add BTCUSDT, ETHUSDT
	Bạn có thể thêm nhiều coin cùng lúc bằng cách phân tách bằng dấu phẩy

/remove [coin1, coin2, ...] - Xóa coin khỏi danh sách theo dõi
	Ví dụ: /remove BTCUSDT, ETHUSDT
	Bạn có thể xóa nhiều coin cùng lúc

/list - Hiển thị danh sách coin hiện tại đang theo dõi

🤖 Hướng dẫn sử dụng:
- Thêm coin vào danh sách để bot theo dõi và gửi thông báo
- Mỗi coin sẽ được phân tích giá và gửi thông báo tự động
- Sử dụng /help để xem hướng dẫn chi tiết bất kỳ lúc nào
"""
	bot.reply_to(message, help_text)

def calculate_limits(lowest_price, highest_price):
	def truncate_to_8(value):
		str_value = str(value)
		index = str_value.find('.')
		if index != -1:
			return str_value[:index+9]
		return str_value

	ratio = highest_price / lowest_price

	if ratio < 1.05:
		return {"lowLimit": "Không", "highLimit": "Không"}
	elif ratio < 1.08:
		return {
			"lowLimit": truncate_to_8(lowest_price * 1.2),
			"highLimit": truncate_to_8(highest_price * 1.3)
		}
	elif ratio < 1.11:
		return {
			"lowLimit": truncate_to_8(lowest_price * 2.2),
			"highLimit": truncate_to_8(highest_price * 2.3)
		}
	elif ratio < 1.15:
		return {
			"lowLimit": truncate_to_8(lowest_price * 3.2),
			"highLimit": truncate_to_8(highest_price * 3.3)
		}
	return {
			"lowLimit": truncate_to_8(lowest_price * 4.2),
			"highLimit": truncate_to_8(highest_price * 4.3)
		}

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
	previous_ratios = load_previous_ratios()
	current_ratios = {}

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

			if response.status_code != 200 or not data or not isinstance(data, list):
				continue

			try:
				formatted_data = []
				for kline in data:
					open_time = datetime.fromtimestamp(int(float(kline[0])) / 1000, tz=utc_tz)
					formatted_time = open_time.strftime('%d.%m.%y - %H:%M')
					low_price = float(kline[3])  # Lowest price
					formatted_kline = [formatted_time, low_price]
					formatted_data.append(formatted_kline)

				# Sort by low price and get 2 lowest and 2 highest
				formatted_data.sort(key=lambda x: x[1])
				
				lowest_2 = formatted_data[:2]
				highest_2 = formatted_data[-2:]

				# Calculate limits
				lowest_price = lowest_2[0][1]
				highest_price = highest_2[-1][1]
				
				# Create message for each record
				alert_message = f"{index}) {symbol}:\n"
				index += 1
				
				# Combine and sort by time
				combined_records = sorted(lowest_2 + highest_2, key=lambda x: x[1])
				
				for i, (time, low) in enumerate(combined_records):
					if i == 2:
						alert_message += "  ...\n"
					alert_message += f"  {time} : {low:.8f}\n"
				
				# Calculate and track ratio
				ratio = highest_price / lowest_price
				current_ratios[symbol] = {
					'ratio': ratio
				}

				# Compare with previous ratio
				if symbol in previous_ratios:
					prev_data = previous_ratios[symbol]
					prev_ratio = prev_data['ratio']

					# Check if previous ratio is within 5-10 minutes
					ratio_change = (ratio - prev_ratio) / prev_ratio * 100

					# Format ratio line - italic if increased
					if ratio_change > 0:
						alert_message += f"\n  Tỉ lệ Cao/Thấp: 🟢 __{ratio:.4f}__ (+{ratio_change:.2f}%)\n"
					elif ratio_change == 0:
						alert_message += f"\n  Tỉ lệ Cao/Thấp: {ratio:.4f}\n"
					else:
						alert_message += f"\n  Tỉ lệ Cao/Thấp: 🔴 {ratio:.4f} ({ratio_change:.2f}%)\n"
				else:
					alert_message += f"\n  Tỉ lệ Cao/Thấp: {ratio:.4f}\n"

				alert_message += "------------------------------"

				alert_messages.append(alert_message)  # Add message to list

			except ValueError:
				print(f"Error converting data to float for {symbol}")
				continue

		except Exception as e:
			print(f"Error checking {symbol}: {e}")

	# Save current ratios for next comparison
	save_previous_ratios(current_ratios)

	# Send messages (existing code remains the same)
	if alert_messages:
		full_alert = f"****** Automatic Telegram Bot Message ******\n"
		full_alert += f"Monitoring data at {datetime.now(utc_tz).strftime('%H:%M - %d.%m.%y')} UTC:\n\n"
		current_message = full_alert
		for message in alert_messages:
			if len(current_message) + len(message) > 4000:
				bot.send_message(chat_id=USER_CHAT_ID, text=current_message, parse_mode='Markdown')
				current_message = full_alert

			current_message += message + "\n"

		if current_message.strip():
			bot.send_message(chat_id=USER_CHAT_ID, text=current_message, parse_mode='Markdown')

TIME_SET = [5, 'm']

def run_schedule():
    while True:
        now = datetime.now()
        if TIME_SET[1] == 's':
            # Gửi liên tục sau mỗi khoảng thời gian được định nghĩa.
            interval_seconds = TIME_SET[0]
            next_run_time = now + timedelta(seconds=interval_seconds)
            wait_time = interval_seconds
        elif TIME_SET[1] == 'm':
            # Gửi ở giây thứ 10 của mỗi bước nhảy phút.
            interval_minutes = TIME_SET[0]
            
            # Calculate the next minute to run
            next_minute = ((now.minute // interval_minutes) + 1) * interval_minutes
            
            # Handle rollover to next hour if needed
            if next_minute >= 60:
                next_minute = next_minute % 60
                next_run_time = (now + timedelta(hours=1)).replace(
                    minute=next_minute,
                    second=20, 
                    microsecond=0
                )
            else:
                next_run_time = now.replace(
                    minute=next_minute,
                    second=20, 
                    microsecond=0
                )
            
            # Nếu thời gian hiện tại đã qua thời gian tính toán, chuyển sang lần tiếp theo.
            if now >= next_run_time:
                next_run_time += timedelta(minutes=interval_minutes)
            
            wait_time = (next_run_time - now).total_seconds()

        print(f"Đợi {wait_time:.2f} giây đến lần chạy tiếp theo lúc {next_run_time.strftime('%H:%M:%S')}.")

        time.sleep(wait_time)
        check_coin_limits()

def start_telegram_bot():
	bot_thread = threading.Thread(target=bot.polling)
	bot_thread.start()

def start_schedule():
	schedule_thread = threading.Thread(target=run_schedule)
	schedule_thread.start()

if __name__ == '__main__':
	start_telegram_bot()
	start_schedule()