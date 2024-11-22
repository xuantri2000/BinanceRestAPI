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

app = Flask(__name__)

API_KEY = 'NFyLaXIvtVQRQGVzItCqhIC895gkJjCHEEABtmxgzY0k2M0PRcqEy1DPLZd4g71a'
API_SECRET = 'UEKO5VV7X8wkSb95qaFSDPb92fIGmdUezvtnWAqqBr5Mj6jOuGWbCL8uwCoTNwa8'
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
        total_days = int(request.json.get('days', 5))

        # Đặt múi giờ UTC
        utc_tz = timezone('UTC')

        # Thời điểm hiện tại theo UTC (bao gồm giờ:phút:giây)
        current_time_utc = datetime.now(utc_tz)
        
        # Thời điểm bắt đầu của ngày hiện tại (00:00:00)
        start_of_today = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Số ngày trong mỗi chunk
        days_per_chunk = 3
        
        # Tính số chunks cần thiết cho dữ liệu lịch sử
        num_chunks = math.ceil(total_days / days_per_chunk)
        
        all_data = []
        
        # Lấy dữ liệu của ngày hiện tại trước
        today_params = {
            'symbol': symbol,
            'interval': '5m',
            'startTime': int(start_of_today.timestamp() * 1000),
            'endTime': int(current_time_utc.timestamp() * 1000),
            'limit': 1000
        }
        
        # Gửi yêu cầu GET cho ngày hiện tại
        response = requests.get(f"{BASE_URL}/klines", params=today_params)
        today_klines = response.json()
        
        # Format dữ liệu ngày hiện tại
        for kline in today_klines:
            try:
                open_time = datetime.fromtimestamp(int(float(kline[0])) / 1000, tz=utc_tz)
            except ValueError:
                return jsonify({'error': f"Invalid data format in kline: {kline[0]}"})

            formatted_time = open_time.strftime('%d.%m.%y - %H:%M')
            formatted_kline = [formatted_time] + kline[1:]
            all_data.append(formatted_kline)

        # Thêm delay nhỏ sau khi lấy dữ liệu ngày hiện tại
        time.sleep(0.1)
        
        # Lấy dữ liệu lịch sử cho các ngày trước đó
        for i in range(num_chunks):
            chunk_end = start_of_today - timedelta(days=i * days_per_chunk)
            chunk_start = chunk_end - timedelta(days=days_per_chunk)
            
            # Đối với chunk cuối, điều chỉnh ngày bắt đầu nếu cần
            if i == num_chunks - 1:
                remaining_days = total_days - (i * days_per_chunk)
                chunk_start = chunk_end - timedelta(days=remaining_days)

            params = {
                'symbol': symbol,
                'interval': '5m',
                'startTime': int(chunk_start.timestamp() * 1000),
                'endTime': int(chunk_end.timestamp() * 1000),
                'limit': 1000
            }
            
            print(params)

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
