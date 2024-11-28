import math
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import requests
import hmac
import hashlib
import time
from pytz import timezone
import time
import requests
import hashlib
import hmac
import urllib.parse
import os
from dotenv import load_dotenv

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
# BASE_URL = 'https://testnet.binance.vision/api/v3'  # Dùng testnet cho các lệnh cần xác thực
BASE_URL = 'https://api.binance.com/api/v3'  # Dùng testnet cho các lệnh cần xác thực

def create_signature(params):
	# Sắp xếp tham số theo thứ tự từ A-Z và mã hóa thành chuỗi truy vấn
	query_string = urllib.parse.urlencode(sorted(params.items()))
	
	# Tạo chữ ký bằng HMAC SHA256 với SECRET_KEY
	signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
	
	return signature

@app.route('/')
def index():
	return render_template('index.html')

@app.route('/get_price', methods=['POST'])
def get_price():
	symbol = request.json.get('symbol', 'BTCUSDT').upper()
	try:
		# Gọi API Binance để lấy 60 cây nến 1 phút gần nhất
		response = requests.get(
			f'{BASE_URL}/klines',
			params={
				'symbol': symbol,
				'interval': '1m',
				'limit': 60
			}
		)
		
		klines = response.json()
		
		if not klines:
			return jsonify({'error': 'No data available'})
		
		prices = {
			'timestamps': [kline[0] for kline in klines],
			'close': [float(kline[4]) for kline in klines]
		}
		return jsonify(prices)
		
	except Exception as e:
		return jsonify({'error': str(e)})

@app.route('/get_current_price', methods=['POST'])
def get_current_price():
	symbol = request.json.get('symbol', 'BTCUSDT').upper()
	try:
		response = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}')
		data = response.json()

		if 'price' not in data:
			return jsonify({'error': 'No data available'})

		prices = {
			'timestamp': int(datetime.now().timestamp() * 1000),
			'close': float(data['price'])
		}
		return jsonify(prices)
		
	except Exception as e:
		return jsonify({'error': str(e)})

@app.route('/place_order', methods=['POST'])
def place_order():
	data = request.json
	symbol = data.get('symbol', '').upper()
	side = data.get('side').upper()
	quantity = float(data.get('quantity'))

	try:
		# Tạo tham số cho yêu cầu
		params = {
			'symbol': symbol,
			'side': side,
			'type': 'MARKET',
			'quantity': quantity,
			'timestamp': int(time.time() * 1000)  # timestamp trong mili giây
		}

		# Tạo chữ ký và thêm vào tham số
		params['signature'] = create_signature(params)

		# Đặt header API key
		headers = {'X-MBX-APIKEY': API_KEY}

		# Gửi yêu cầu POST đến API Binance
		response = requests.post(f"{BASE_URL}/order", headers=headers, params=params)

		# Trả về kết quả phản hồi từ Binance API
		return jsonify(response.json())

	except Exception as e:
		return jsonify({'error': str(e)})


@app.route('/get_orders', methods=['POST'])
def get_orders():
	try:
		symbol = request.json.get('symbol', '').upper()
		if not symbol:
			return jsonify({'error': 'Symbol is required'}), 400

		params = {
			'symbol': symbol,
			'timestamp': int(time.time() * 1000)
		}
		params['signature'] = create_signature(params)

		headers = {'X-MBX-APIKEY': API_KEY}
		response = requests.get(f"{BASE_URL}/allOrders", headers=headers, params=params)
		
		return jsonify(response.json())
	except Exception as e:
		return jsonify({'error': str(e)})

@app.route('/get_historical_data', methods=['POST'])
def get_historical_data():
    try:
        symbol = request.json.get('symbol', '').upper()
        days = int(request.json.get('days', 5))  # days bây giờ sẽ là tổng số ngày luôn

        # Đặt múi giờ UTC
        utc_tz = timezone('UTC')

        # Thời điểm hiện tại theo UTC
        current_time_utc = datetime.now(utc_tz)
        
        # Thời điểm bắt đầu (n-1 ngày trước, tính từ đầu ngày)
        start_time = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1)
        
        # Số ngày trong mỗi chunk
        days_per_chunk = 3
        
        # Tính số chunks cần thiết
        num_chunks = math.ceil(days / days_per_chunk)
        
        all_data = []
        
        # Lặp qua từng chunk để lấy dữ liệu
        for i in range(num_chunks):
            if i == 0:
                # Chunk đầu tiên lấy đến thời điểm hiện tại
                chunk_end = current_time_utc
            else:
                # Các chunk khác lấy đến cuối ngày
                days_back = i * days_per_chunk
                chunk_end = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back-1)
            
            # Tính thời điểm bắt đầu của chunk
            if i == num_chunks - 1:
                # Chunk cuối cùng bắt đầu từ start_time
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
            
            # print(f"Chunk {i + 1}/{num_chunks}:")
            # print(f"Start: {chunk_start}")
            # print(f"End: {chunk_end}")
            # print("Params:", params)
            # print("---")

            # Gửi yêu cầu GET đến Binance API
            response = requests.get(f"{BASE_URL}/klines", params=params)
            klines = response.json()

            # Format dữ liệu cho chunk hiện tại
            for kline in klines:
                try:
                    open_time = datetime.fromtimestamp(int(float(kline[0])) / 1000, tz=utc_tz)
                except ValueError:
                    return jsonify({'error': f"Invalid data format in kline: {kline[0]}"})

                formatted_time = open_time.strftime('%d.%m.%y - %H:%M')
                formatted_kline = [formatted_time] + kline[1:]
                all_data.append(formatted_kline)

            # Thêm một khoảng delay nhỏ giữa các request
            if i < num_chunks - 1:
                time.sleep(0.1)

        # Sắp xếp lại dữ liệu theo thời gian
        all_data.sort(key=lambda x: datetime.strptime(x[0], '%d.%m.%y - %H:%M'))

        return jsonify(all_data)

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
	app.run(debug=True)
