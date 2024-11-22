let chart;
let updateInterval;
let priceUpdateInterval; // Biến để lưu interval của updatePrice
let symbol;

function startChart() {
    // Clear any existing intervals
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    if (priceUpdateInterval) {
        clearInterval(priceUpdateInterval);
    }

    symbol = document.getElementById('symbol').value.toUpperCase();
    if (!symbol) {
        alert("Please enter a coin symbol");
        return;
    }

    // document.getElementById('orderSymbol').value = symbol;

    // Enable stop button
    document.getElementById('stopButton').disabled = false;

    // Clear the existing chart before creating a new one
    if (chart) {
        chart.destroy(); // Destroy the current chart instance
        chart = null; // Reset the chart object
    }

    // Initial chart update
    updateChart();

    // Set interval to update every 1 minute (60000 milliseconds)
    updateInterval = setInterval(updateChart, 60000);

    // Call updatePrice every second if symbol is valid
    priceUpdateInterval = setInterval(() => updatePrice(symbol), 1000);

    loadOrders(symbol);
}


function stopChart() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
    if (priceUpdateInterval) {
        clearInterval(priceUpdateInterval);
        priceUpdateInterval = null;
    }
    document.getElementById('stopButton').disabled = true;
}

async function updateChart() {
    try {
        const response = await fetch('/get_price', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol })
        });

        const data = await response.json();
        if (data.error) {
            alert(data.error);
            stopChart(); // Stop chart update and price updates
            return;
        }

        // Format timestamps to HH:mm format
        const labels = data.timestamps.map(ts => {
            const date = new Date(ts);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        });

        // If chart already exists, update it with new data
        if (chart) {
            // Add new label and data point
            chart.data.labels.push(labels[labels.length - 1]);
            chart.data.datasets[0].data.push(data.close[data.close.length - 1]);

            // If the chart has more than 15 labels, remove the first one
            if (chart.data.labels.length > 15) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }

            // Update the chart with new data
            chart.update('none');
        } else {
            // Create new chart if it doesn't exist yet
            const ctx = document.getElementById('priceChart').getContext('2d');
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: `${symbol} Price (Last Hour)`,
                        data: data.close,
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        fill: true,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            ticks: {
                                callback: function(value) {
                                    return value.toFixed(2);
                                }
                            }
                        },
                        x: {
                            ticks: {
                                maxTicksLimit: 15
                            }
                        }
                    },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Price: ${context.parsed.y.toFixed(8)}`;
                                }
                            }
                        },
                        title: {
                            display: true,
                            text: 'Price Chart (1-minute intervals)'
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error updating chart:', error);
    }
}


async function updatePrice(symbol) {
    try {
        const response = await fetch('/get_current_price', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol })
        });

        const data = await response.json();
        // console.log(data)
        if (data.error) {
            alert(data.error); // Show error if symbol is invalid
            clearInterval(priceUpdateInterval); // Stop further price updates
            return;
        }

        currentPrice = data.close; // Current price (latest closing price)

        // Update price display
        const lastUpdateTime = new Date().toLocaleTimeString();
        document.getElementById('currentTime').innerHTML = `${lastUpdateTime}`;
        document.getElementById('currentPrice').innerHTML = `<span >${currentPrice}</span>`;
    } catch (error) {
        console.error('Error updating price:', error);
    }
}

async function placeOrder(event) {
    event.preventDefault();
    const orderSymbol = document.getElementById('orderSymbol').value.toUpperCase();
    const side = document.getElementById('orderSide').value;
    const quantity = document.getElementById('orderQuantity').value;

    try {
        const response = await fetch('/place_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: orderSymbol, side, quantity })
        });

        const data = await response.json();
        if (data.error) {
            alert(data.error);
        } else {
            alert("Order placed successfully!");
            loadOrders(orderSymbol);
        }
    } catch (error) {
        console.error("Error placing order:", error);
        alert("Error placing order. Please try again.");
    }
}

async function loadOrders(symbol) {
    try {
		document.getElementById('orderSymbol').value = symbol;

        const response = await fetch('/get_orders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol })
        });

        const orders = await response.json();

        const orderTable = document.getElementById('orderTable');
        orderTable.innerHTML = '';

        if (!orders || orders.length === 0) {
            console.log('No orders available.');
            return;
        }

        orders.forEach(order => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${order.symbol}</td>
                <td>${order.side}</td>
                <td>${order.origQty}</td>
                <td>${order.price || 'Market Price'}</td>
                <td>${order.status}</td>
            `;
            orderTable.appendChild(row);
        });
    } catch (error) {
        console.error("Error loading orders:", error);
    }
}

async function searchHistorical() {
    const symbol = document.getElementById('histSymbol').value.toUpperCase();
    const days = parseInt(document.getElementById('histDays').value);
    
    if (!symbol) {
        alert("Please enter a symbol");
        return;
    }

    try {
        // showLoading(); // Giả sử bạn có hàm này để hiển thị loading indicator

        const response = await fetch('/get_historical_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol, days })
        });

        const data = await response.json();
        
        // hideLoading(); // Giả sử bạn có hàm này để ẩn loading indicator
        
        if (data.error) {
            alert(data.error);
            return;
        }

        console.log(data);
        displayHistoricalData(data);
    } catch (error) {
        // hideLoading();
        console.error('Error fetching historical data:', error);
        alert('Error fetching historical data');
    }
}

function displayHistoricalData(data) {
    const container = document.getElementById('historicalData');
    container.innerHTML = '';

    data.length -= 1;
    const columnsPerTable = 4;

    // Nhóm dữ liệu theo ngày
    const groupedByDay = {};
    data.forEach(record => {
        const dateStr = record[0].split(" - ")[0];
        const date = dateStr.split(" ")[0];
        if (!groupedByDay[date]) {
            groupedByDay[date] = [];
        }
        groupedByDay[date].push(record);
    });

    const days = Object.keys(groupedByDay);
    const numberOfTables = Math.ceil(days.length / columnsPerTable);

    for (let tableIndex = 0; tableIndex < numberOfTables; tableIndex++) {
        const tableContainer = document.createElement('div');
        tableContainer.style.marginBottom = '30px';

        const table = document.createElement('table');
        table.style.borderCollapse = 'collapse';
        table.style.width = '100%';

        const sortButtonRow = document.createElement('tr');
        const headerRow = document.createElement('tr');
        const dataRow = document.createElement('tr');

        for (let col = 0; col < columnsPerTable; col++) {
            const dayIndex = tableIndex * columnsPerTable + col;
            
            if (dayIndex < days.length) {
                const currentDate = days[dayIndex];
                const dayData = groupedByDay[currentDate];

                // Tạo ô chứa nút sort
                const sortTh = document.createElement('th');
                sortTh.style.padding = '5px';
                sortTh.style.border = '1px solid #ddd';
                
                const buttonContainer = document.createElement('div');
                buttonContainer.style.display = 'flex';
                buttonContainer.style.gap = '5px';
                buttonContainer.style.justifyContent = 'center';
                buttonContainer.style.flexWrap = 'wrap';

                // Các nút sort
                const ascButton = document.createElement('button');
                ascButton.textContent = '↑ Giá';
                ascButton.style.padding = '5px';
                
                const descButton = document.createElement('button');
                descButton.textContent = '↓ Giá';
                descButton.style.padding = '5px';
                
                const timeButton = document.createElement('button');
                timeButton.textContent = '⌚ Giờ';
                timeButton.style.padding = '5px';

                const highButton = document.createElement('button');
                highButton.textContent = '↟ Cao';
                highButton.style.padding = '5px';
                highButton.classList.add('active');

                const lowButton = document.createElement('button');
                lowButton.textContent = '↡ Thấp';
                lowButton.style.padding = '5px';

                buttonContainer.appendChild(highButton);
                buttonContainer.appendChild(lowButton);
                buttonContainer.appendChild(ascButton);
                buttonContainer.appendChild(descButton);
                buttonContainer.appendChild(timeButton);
                sortTh.appendChild(buttonContainer);
                sortButtonRow.appendChild(sortTh);

                // Tạo tiêu đề ngày
                const th = document.createElement('th');
                th.textContent = currentDate;
                th.style.padding = '10px';
                th.style.border = '1px solid #ddd';
                th.style.backgroundColor = '#f4f4f4';
                headerRow.appendChild(th);

                // Tạo ô chứa textarea
                const td = document.createElement('td');
                td.style.border = '1px solid #ddd';

                // Tạo textarea
                const textarea = document.createElement('textarea');

                // Chuyển đổi dữ liệu ngày thành định dạng hiển thị
                const formattedDayData = dayData.map(record => ({
                    time: record[0],
                    highPrice: parseFloat(record[2]), // Giá cao
                    lowPrice: parseFloat(record[3]), // Giá thấp
                    displayHigh: `${record[0]} : ${parseFloat(record[2]).toFixed(8)}`,
                    displayLow: `${record[0]} : ${parseFloat(record[3]).toFixed(8)}`
                }));

                // State để theo dõi mode hiển thị hiện tại
                let currentPriceMode = 'high'; // 'high' hoặc 'low'

                // Function để lấy giá theo mode hiện tại
                const getCurrentPrice = (item) => {
                    return currentPriceMode === 'high' ? item.highPrice : item.lowPrice;
                };

                // Function để lấy display text theo mode hiện tại
                const getCurrentDisplay = (item) => {
                    return currentPriceMode === 'high' ? item.displayHigh : item.displayLow;
                };

                // Function để update textarea
                const updateTextarea = (data, sortType = 'asc') => {
                    let sortedData = [...data];
                    
                    switch(sortType) {
                        case 'asc':
                            sortedData.sort((a, b) => getCurrentPrice(a) - getCurrentPrice(b));
                            break;
                        case 'desc':
                            sortedData.sort((a, b) => getCurrentPrice(b) - getCurrentPrice(a));
                            break;
                        case 'time':
                            // Giữ nguyên thứ tự ban đầu
                            break;
                    }

                    textarea.value = sortedData.map(item => getCurrentDisplay(item)).join('\n');
                };

                // Function để cập nhật trạng thái active của buttons
                const updateButtonState = (activeButton) => {
                    highButton.classList.remove('active');
                    lowButton.classList.remove('active');
                    activeButton.classList.add('active');
                };

                // Thêm style cho button active
                const style = document.createElement('style');
                style.textContent = `
                    button.active {
                        background-color: #007bff;
                        color: white;
                    }
                `;
                document.head.appendChild(style);

                // Event listeners cho các nút
                highButton.addEventListener('click', () => {
                    currentPriceMode = 'high';
                    updateButtonState(highButton);
                    updateTextarea(formattedDayData, 'asc');
                });

                lowButton.addEventListener('click', () => {
                    currentPriceMode = 'low';
                    updateButtonState(lowButton);
                    updateTextarea(formattedDayData, 'asc');
                });

                ascButton.addEventListener('click', () => {
                    updateTextarea(formattedDayData, 'asc');
                });

                descButton.addEventListener('click', () => {
                    updateTextarea(formattedDayData, 'desc');
                });

                timeButton.addEventListener('click', () => {
                    updateTextarea(formattedDayData, 'time');
                });

                // Định dạng textarea
                textarea.style.width = '97%';
                textarea.style.height = '400px';
                textarea.style.border = '1px solid #ddd';
                textarea.style.resize = 'vertical';
                textarea.setAttribute('readonly', true);

                // Khởi tạo hiển thị mặc định với giá cao nhất, sắp xếp tăng dần
                updateTextarea(formattedDayData, 'asc');

                td.appendChild(textarea);
                dataRow.appendChild(td);
            }
        }

        // Thêm các hàng vào bảng
        table.appendChild(sortButtonRow);
        table.appendChild(headerRow);
        table.appendChild(dataRow);

        // Tạo tiêu đề cho bảng
        const tableStartDay = days[tableIndex * columnsPerTable];
        const tableEndDay = days[Math.min((tableIndex + 1) * columnsPerTable - 1, days.length - 1)];

        const tableName = document.createElement('div');
        tableName.style.marginBottom = '10px';
        tableName.style.fontWeight = 'bold';
        tableName.textContent = `Bảng dữ liệu từ ngày ${tableStartDay} đến ngày ${tableEndDay}`;

        tableContainer.appendChild(tableName);
        tableContainer.appendChild(table);
        container.appendChild(tableContainer);
    }
}

let openPrice = null;
let currentPrice = null;

window.onbeforeunload = function() {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    if (priceUpdateInterval) {
        clearInterval(priceUpdateInterval);
    }
};
