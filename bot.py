import math
import os
import time
from flask import jsonify, request
import requests
import telebot
import json
import threading
import schedule
from datetime import datetime, timedelta
from pytz import timezone
from dotenv import load_dotenv
import socket

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

def is_connected():
    try:
        # Kiểm tra kết nối tới Google DNS (hoặc một host đáng tin cậy khác)
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False
    
def load_previous_ratios():
    if os.path.exists(PREVIOUS_RATIO_FILE):
        with open(PREVIOUS_RATIO_FILE, 'r') as f:
            try:
                ratios = json.load(f)
                return ratios
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
        # Lọc bỏ các dòng trống và chuẩn hóa dữ liệu
        coins = [coin.strip().upper() for coin in f.readlines() if coin.strip()]
    
    # Ghi danh sách đã loại bỏ dòng trống trở lại tệp
    with open(CHECKLIST_FILE, 'w') as f:
        for coin in coins:
            f.write(f"{coin}\n")
    
    return coins

def write_coin_list(coins):
    with open(CHECKLIST_FILE, 'w') as f:
        for coin in coins:
            f.write(f"{coin.upper()}\n")

# Thêm handler để lưu chat_id khi start bot
@bot.message_handler(commands=['start'])
def start_handler(message):
    global USER_CHAT_ID
    USER_CHAT_ID = message.chat.id

    # Thêm giờ trong thông báo bắt đầu
    utc_tz = timezone('UTC')
    current_time_utc = datetime.now(utc_tz).strftime('%H:%M - %d.%m.%y')
    bot.reply_to(message, f"Bắt đầu theo dõi coin theo danh sách lúc {current_time_utc} UTC.")

    try:
        # Đọc danh sách coin hiện tại từ checklist.txt
        current_coins = read_coin_list()
        if not current_coins:
            bot.reply_to(message, "Danh sách coin trống. Vui lòng thêm coin bằng lệnh /add.")
            return

        # Lấy dữ liệu tỷ lệ theo thời gian thực
        chunk_start = datetime.now(utc_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        chunk_end = datetime.now(utc_tz)

        previous_ratios = {}  # Khởi tạo dữ liệu mới cho previous_ratios
        failed_coins = []  # Danh sách các coin không lấy được dữ liệu

        for symbol in current_coins:
            try:
                params = {
                    'symbol': symbol,
                    'interval': '5m',
                    'startTime': int(chunk_start.timestamp() * 1000),
                    'endTime': int(chunk_end.timestamp() * 1000),
                    'limit': 500
                }
                response = fetch_binance_data(f"{BASE_URL}/klines", params=params)
                data = response.json()

                if response.status_code != 200 or not data or not isinstance(data, list):
                    failed_coins.append(symbol)
                    continue

                # Tính tỷ lệ cao/thấp (ratio)
                formatted_data = []
                for kline in data:
                    low_price = float(kline[3])  # Lowest price
                    formatted_data.append(low_price)

                if formatted_data:
                    lowest_price = min(formatted_data)
                    highest_price = max(formatted_data)
                    ratio = highest_price / lowest_price

                    # Lưu vào previous_ratios
                    previous_ratios[symbol] = {
                        'ratio': ratio, 
                        'tracking_time': datetime.now(utc_tz).strftime('%d.%m.%y - %H:%M')
                    }
            except Exception as e:
                print(f"Lỗi khi xử lý coin {symbol}: {e}")
                failed_coins.append(symbol)

        # Lưu dữ liệu mới vào tệp previous_ratios
        save_previous_ratios(previous_ratios)

        # Gửi thông báo về các coin không lấy được dữ liệu
        if failed_coins:
            response_message = "Không thể lấy dữ liệu cho các coin sau:\n" + "\n".join(failed_coins)
            bot.reply_to(message, response_message)

    except Exception as e:
        print(f"Lỗi: {str(e)}")

@bot.message_handler(commands=['status'])
def status_coins(message):
    previous_ratios = load_previous_ratios()
    
    if not previous_ratios:
        bot.reply_to(message, "Chưa có dữ liệu theo dõi coin.")
        return
    
    status_message = "Tracking time:\n\n"
    for symbol, data in previous_ratios.items():
        status_message += f"{symbol}:\n"
        status_message += f"  Tỉ lệ Cao/Thấp: {data['ratio']:.4f}\n"
        status_message += f"  Lần ghi cuối: {data.get('tracking_time', 'Không có dữ liệu')}\n\n"
    
    # Split long status message if needed
    split_messages = split_long_message(status_message)
    for msg in split_messages:
        bot.reply_to(message, msg)

@bot.message_handler(commands=['add'])
def add_coins(message):
    try:
        # Lấy danh sách các coin cần thêm
        coins_to_add = [coin.strip().upper() for coin in message.text.split('/add')[1].replace(',', '\n').split('\n') if coin.strip()]
        current_coins = read_coin_list()
        response_message = ""
        utc_tz = timezone('UTC')
        current_time_utc = datetime.now(utc_tz)

        # Xác định các coin mới và các coin đã tồn tại
        newly_added = [coin for coin in coins_to_add if coin not in current_coins]
        existing_coins = [coin for coin in coins_to_add if coin in current_coins]

        # Nếu có coin đã tồn tại, thông báo cho người dùng
        if existing_coins:
            response_message += "Các coin sau đã tồn tại trong danh sách:\n" + "\n".join(existing_coins) + "\n"

        # Thêm các coin mới vào danh sách
        current_coins += newly_added

        # Ghi danh sách cập nhật vào file
        write_coin_list(current_coins)

        # Kiểm tra tính hợp lệ của các coin mới
        invalid_coins = []
        chunk_start = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        chunk_end = current_time_utc

        previous_ratios = load_previous_ratios()

        for symbol in newly_added:
            try:
                params = {
                    'symbol': symbol,
                    'interval': '5m',
                    'startTime': int(chunk_start.timestamp() * 1000),
                    'endTime': int(chunk_end.timestamp() * 1000),
                    'limit': 500
                }
                response = fetch_binance_data(f"{BASE_URL}/klines", params=params)
                data = response.json()

                if response.status_code != 200 or not data or not isinstance(data, list):
                    invalid_coins.append(symbol)
                    continue

                # Tính tỷ lệ cao/thấp
                formatted_data = []
                for kline in data:
                    low_price = float(kline[3])  # Lowest price
                    formatted_data.append(low_price)

                if formatted_data:
                    lowest_price = min(formatted_data)
                    highest_price = max(formatted_data)
                    ratio = highest_price / lowest_price
                    previous_ratios[symbol] = {
                        'ratio': ratio, 
                        'tracking_time': current_time_utc.strftime('%d.%m.%y - %H:%M')
                    }

            except Exception as e:
                print(f"Lỗi khi kiểm tra coin {symbol}: {e}")
                invalid_coins.append(symbol)

        # Lưu lại previous_ratios nếu có thay đổi
        save_previous_ratios(previous_ratios)

        # Loại bỏ các coin không hợp lệ khỏi file và thông báo
        if invalid_coins:
            current_coins = [coin for coin in current_coins if coin not in invalid_coins]
            write_coin_list(current_coins)
            response_message += "Các coin sau không hợp lệ và đã bị xóa:\n" + "\n".join(invalid_coins)
        else:
            response_message += "Đã thêm và cập nhật các coin sau lúc " + current_time_utc.strftime('%H:%M - %d.%m.%y') + ":\n" + "\n".join(newly_added)

        bot.reply_to(message, response_message)
    except Exception as e:
        print(f"Lỗi: {str(e)}")

@bot.message_handler(commands=['remove'])
def remove_coins(message):
    try:
        # Lấy danh sách các coin cần xóa
        coins_to_remove = [coin.strip().upper() for coin in message.text.split('/remove')[1].replace(',', '\n').split('\n') if coin.strip()]
        current_coins = read_coin_list()

        # Xác định các coin thực sự tồn tại trong danh sách hiện tại
        valid_coins_to_remove = [coin for coin in coins_to_remove if coin in current_coins]

        # Cập nhật danh sách coin
        updated_coins = [coin for coin in current_coins if coin not in valid_coins_to_remove]
        write_coin_list(updated_coins)

        # Xóa các coin hợp lệ khỏi previous_ratios
        previous_ratios = load_previous_ratios()
        for coin in valid_coins_to_remove:
            if coin in previous_ratios:
                del previous_ratios[coin]
        save_previous_ratios(previous_ratios)

        # Tạo phản hồi
        if valid_coins_to_remove:
            response = "Đã xóa các coin sau:\n" + "\n".join(valid_coins_to_remove)
        else:
            response = "Không có coin nào trong danh sách cần xóa."

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
    
def split_long_message(message, max_length=4096):
    """
    Split a long message into multiple messages of specified max length.
    Telegram has a 4096 character limit per message.
    """
    messages = []
    while message:
        # If message is shorter than max length, add it and break
        if len(message) <= max_length:
            messages.append(message)
            break
        
        # Try to split at a newline close to max length
        split_index = message.rfind('\n', 0, max_length)
        
        # If no newline found, just cut at max length
        if split_index == -1:
            split_index = max_length
        
        # Add the first part to messages
        messages.append(message[:split_index])
        
        # Remove the first part from the message
        message = message[split_index:].lstrip()
    
    return messages

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

/status - Hiển thị lần cập nhật cuối trong file tỉ lệ cao/thấp

/track [coin] [days] - Theo dõi coin trong vòng [days] ngày

🤖 Hướng dẫn sử dụng:
- Thêm coin vào danh sách để bot theo dõi và gửi thông báo
- Mỗi coin sẽ được phân tích giá và gửi thông báo tự động
- Sử dụng /help để xem hướng dẫn chi tiết bất kỳ lúc nào
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['track'])
def track_command(message):
    try:
        # Parse command input
        command_parts = message.text.split()
        if len(command_parts) != 3:
            bot.reply_to(message, "Cú pháp không đúng. Vui lòng nhập: /track <symbol> <days>")
            return

        symbol = command_parts[1].upper()
        try:
            days = int(command_parts[2])
            if days <= 0:
                raise ValueError
        except ValueError:
            bot.reply_to(message, "Số ngày phải là một số nguyên dương.")
            return

        # Call get_historical_data
        historical_data = get_historical_data(symbol, days)

        if 'error' in historical_data:
            bot.reply_to(message, f"Đã xảy ra lỗi: Kiểm tra lại tên symbol")
            return

        # Process data to calculate high/low details per day
        daily_stats = {}
        for kline in historical_data:
            date, time = kline[0].split(' - ')  # Extract date and time (dd.mm.yy - hh:mm)
            low_price = float(kline[3])  # Column 4 is the Low price

            if date not in daily_stats:
                daily_stats[date] = {
                    'lows': [],
                    'ratios': []
                }
            
            daily_stats[date]['lows'].append((time, low_price))

        # Process ratios and prepare for sorting
        ratio_sorted_dates = []
        for date, stats in daily_stats.items():
            # Sort low prices
            sorted_lows = sorted(stats['lows'], key=lambda x: x[1])
            
            # Get 2 lowest and 2 highest prices
            lowest_2 = sorted_lows[:2]
            highest_2 = sorted_lows[-2:]
            
            # Calculate ratio
            ratio = highest_2[-1][1] / lowest_2[0][1] if lowest_2[0][1] > 0 else 0
            
            ratio_sorted_dates.append((date, ratio, lowest_2, highest_2))
        
        # Sort by ratio in descending order
        ratio_sorted_dates.sort(key=lambda x: x[1], reverse=True)

        # Log tracking start
        utc_tz = timezone('UTC')
        current_time = datetime.now(utc_tz).strftime('%Y-%m-%d %H:%M:%S')
        result_message = f"**** Tracking {symbol} at {current_time} ****\n\n"

        # Display results with numbered order
        for rank, (date, ratio, lowest_2, highest_2) in enumerate(ratio_sorted_dates, 1):
            # Create the day's entry
            day_entry = f"{rank}) {date}\n"
            
            # Add 2 lowest prices
            for time, low in lowest_2:
                day_entry += f"  {date} - {time} : {low:.8f}\n"
            
            day_entry += "  .....\n"
            
            # Add 2 highest prices
            for time, high in highest_2:
                day_entry += f"  {date} - {time} : {high:.8f}\n"
            
            day_entry += f"  Tỷ lệ Cao/Thấp: {ratio:.4f}\n\n"
            
            result_message += day_entry

        # Split long message and send multiple messages if needed
        split_messages = split_long_message(result_message)
        for msg in split_messages:
            bot.reply_to(message, msg)

    except Exception as e:
        bot.reply_to(message, f"Đã xảy ra lỗi: {str(e)}")

def get_historical_data(symbol, days):
    try:
        # Đặt múi giờ UTC
        utc_tz = timezone('UTC')

        # Thời điểm hiện tại theo UTC
        current_time_utc = datetime.now(utc_tz)

        # Thời điểm bắt đầu (n-1 ngày trước, tính từ đầu ngày)
        start_time = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        # Số ngày trong mỗi chunk
        days_per_chunk = 3

        # Tính số chunks cần thiết
        num_chunks = math.ceil(days / days_per_chunk)

        all_data = []

        # Lặp qua từng chunk để lấy dữ liệu
        for i in range(num_chunks):
            if i == 0:
                chunk_end = current_time_utc
            else:
                days_back = i * days_per_chunk
                chunk_end = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back - 1)

            if i == num_chunks - 1:
                chunk_start = start_time
            else:
                chunk_start = chunk_end - timedelta(days=days_per_chunk)

            params = {
                'symbol': symbol,
                'interval': '5m',
                'startTime': int(chunk_start.timestamp() * 1000),
                'endTime': int(chunk_end.timestamp() * 1000),
                'limit': 1000
            }

            response = fetch_binance_data(f"{BASE_URL}/klines", params=params)
            klines = response.json()

            for kline in klines:
                try:
                    open_time = datetime.fromtimestamp(int(float(kline[0])) / 1000, tz=utc_tz)
                except ValueError:
                    return {'error': f"Vui lòng kiểm tra lại tên symbol: " + symbol}

                formatted_time = open_time.strftime('%d.%m.%y - %H:%M')
                formatted_kline = [formatted_time] + kline[1:]
                all_data.append(formatted_kline)

            if i < num_chunks - 1:
                time.sleep(0.1)

        all_data.sort(key=lambda x: datetime.strptime(x[0], '%d.%m.%y - %H:%M'))
        return all_data

    except Exception as e:
        return {'error': str(e)}

def check_coin_limits():
    global USER_CHAT_ID
    if USER_CHAT_ID is None:
        return  # Exit if no chat_id

    coins = read_coin_list()
    utc_tz = timezone('UTC')
    current_time_utc = datetime.now(utc_tz)
    
	# Kiểm tra nếu là đúng 00:00 UTC
    if current_time_utc.hour == 0 and current_time_utc.minute == 0 and current_time_utc.second == 5:
        # Reset toàn bộ ratios về 1.0
        previous_ratios = {symbol: {'ratio': 1.0, 'tracking_time': current_time_utc.strftime('%d.%m.%y - %H:%M')} for symbol in read_coin_list()}
        save_previous_ratios(previous_ratios)
        bot.send_message(chat_id=USER_CHAT_ID, text="Thời gian mốc 00:00, toàn bộ symbol trả về 1.0!!!!", parse_mode='Markdown')
        return
    
    chunk_start = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    chunk_end = current_time_utc

    alert_messages = []  # List to store messages
    previous_ratios = load_previous_ratios()
    current_ratios = {}
    has_significant_increase = False

    for symbol in coins:
        try:
            params = {
                'symbol': symbol,
                'interval': '5m',
                'startTime': int(chunk_start.timestamp() * 1000),
                'endTime': int(chunk_end.timestamp() * 1000),
                'limit': 500
            }
            response = fetch_binance_data(f"{BASE_URL}/klines", params=params)
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
                
                # Calculate and track ratio
                ratio = highest_price / lowest_price
                current_ratios[symbol] = {
                    'ratio': ratio,
                    'tracking_time': datetime.now(utc_tz).strftime('%d.%m.%y - %H:%M')
                }
                
                # Create message for this symbol
                alert_message = f"{symbol}:\n"
                
                # Combine and sort by time
                combined_records = sorted(lowest_2 + highest_2, key=lambda x: x[1])
                
                for i, (time, low) in enumerate(combined_records):
                    if i == 2:
                        alert_message += "  ...\n"
                    alert_message += f"  {time} : {low:.8f}\n"

                # Kiểm tra và format ratio
                if symbol not in previous_ratios:
                    # Nếu symbol chưa từng có trong previous_ratios
                    alert_message += f"\n  Tỉ lệ Cao/Thấp: {ratio:.4f}\n"
                    previous_ratios[symbol] = current_ratios[symbol]
                else:
                    # Nếu symbol đã có trong previous_ratios
                    prev_data = previous_ratios[symbol]
                    prev_ratio = prev_data['ratio']

                    # Determine if the ratio has increased
                    is_increased = ratio >= (prev_ratio + 0.01)

                    ratio_change = (ratio - prev_ratio) / prev_ratio * 100
                    print(f'{symbol} : {ratio} ({ratio_change}%)')
                    
                    if is_increased:
                        alert_message += f"\n  Tỉ lệ Cao/Thấp: 🟢 {ratio:.4f} (+{ratio_change:.2f}%)\n"
                        has_significant_increase = True
                        previous_ratios[symbol] = current_ratios[symbol]
                    else:
                        alert_message += f"\n  Tỉ lệ Cao/Thấp: {ratio:.4f}\n"

                alert_message += "------------------------------"
                
                # Thêm thông tin ratio vào message để dễ sắp xếp
                alert_messages.append({
                    'message': alert_message, 
                    'ratio': ratio
                })

            except ValueError:
                print(f"Error converting data to float for {symbol}")
                continue

        except Exception as e:
            print(f"Error checking {symbol}: {e}")

    # Lưu lại previous_ratios với các coin đã thay đổi
    save_previous_ratios(previous_ratios)

    # Chỉ lưu và gửi thông báo nếu có sự thay đổi
    if has_significant_increase and alert_messages:
        # Sắp xếp messages theo ratio giảm dần
        sorted_messages = sorted(alert_messages, key=lambda x: x['ratio'], reverse=True)

        full_alert = f"****** Automatic Telegram Bot Message ******\n"
        full_alert += f"Monitoring data at {datetime.now(utc_tz).strftime('%H:%M - %d.%m.%y')} UTC:\n\n"
        current_message = full_alert
        
        # Thêm index sau khi sắp xếp
        for index, item in enumerate(sorted_messages, 1):
            message = f"{index}) " + item['message']
            if len(current_message) + len(message) > 4000:
                bot.send_message(chat_id=USER_CHAT_ID, text=current_message, parse_mode='Markdown')
                current_message = full_alert

            current_message += message + "\n"

        if current_message.strip():
            bot.send_message(chat_id=USER_CHAT_ID, text=current_message, parse_mode='Markdown')

TIME_SET = [5, 'm']

def run_schedule():
    while True:
        if is_connected():
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
                        second=5, 
                        microsecond=0
                    )
                else:
                    next_run_time = now.replace(
                        minute=next_minute,
                        second=5, 
                        microsecond=0
                    )
                
                # Nếu thời gian hiện tại đã qua thời gian tính toán, chuyển sang lần tiếp theo.
                if now >= next_run_time:
                    next_run_time += timedelta(minutes=interval_minutes)
                
                wait_time = (next_run_time - now).total_seconds()

            print(f"Đợi {wait_time:.2f} giây đến lần chạy tiếp theo lúc {next_run_time.strftime('%H:%M:%S')}.")

            time.sleep(wait_time)
            check_coin_limits()
        else:
            print("Mất mạng, chờ kết nối lại...")
            time.sleep(5)

def start_telegram_bot():
    def polling():
        while True:
            if is_connected():
                try:
                    print("Đang khởi động bot...")
                    bot.polling(non_stop=True, interval=0)
                    print("Bot đang chạy!")
                    break  # Thoát khỏi vòng lặp khi polling thành công
                except Exception as e:
                    print(f"Lỗi bot.polling: {e}. Thử lại sau...")
                    time.sleep(5)
            else:
                print("Mất mạng, chờ kết nối lại...")
                time.sleep(5)

    # Chạy polling trong một luồng riêng
    bot_thread = threading.Thread(target=polling, daemon=True)
    bot_thread.start()
            
def fetch_binance_data(url, params):
    while True:
        if is_connected():
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()  # Kiểm tra lỗi HTTP
                return response
            except Exception as e:
                print(f"Lỗi API Binance: {e}")
                break
        else:
            print("Mất mạng, chờ kết nối lại...")
            time.sleep(5)

def start_schedule():
    schedule_thread = threading.Thread(target=run_schedule)
    schedule_thread.start()

if __name__ == '__main__':
    start_telegram_bot()
    start_schedule()