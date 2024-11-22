let chart;
let updateInterval;
let priceUpdateInterval; // Biến để lưu interval của updatePrice
let symbol;

function startChart(symbol) {
    // Clear any existing intervals
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    if (priceUpdateInterval) {
        clearInterval(priceUpdateInterval);
    }

    // Call updatePrice every second if symbol is valid
    priceUpdateInterval = setInterval(() => updatePrice(symbol), 1000);
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

async function searchHistorical() {
    const symbol = document.getElementById('histSymbol').value.toUpperCase();
    const days = parseInt(document.getElementById('histDays').value);
    
    if (!symbol) {
        alert("Please enter a symbol");
        return;
    }

	startChart(symbol);

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
    const columnsPerTable = window.innerWidth < 768 ? 1 : 3;

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
        tableContainer.className = 'mb-5';

        const tableTitle = document.createElement('h5');
        const tableStartDay = days[tableIndex * columnsPerTable];
        const tableEndDay = days[Math.min((tableIndex + 1) * columnsPerTable - 1, days.length - 1)];
        tableTitle.className = 'mb-3';
        tableTitle.textContent = `Data from ${tableStartDay} to ${tableEndDay}`;
        tableContainer.appendChild(tableTitle);

        const row = document.createElement('div');
        row.className = 'row g-4';

        for (let col = 0; col < columnsPerTable; col++) {
            const dayIndex = tableIndex * columnsPerTable + col;
            
            if (dayIndex < days.length) {
                const currentDate = days[dayIndex];
                const dayData = groupedByDay[currentDate];

                const colDiv = document.createElement('div');
                colDiv.className = window.innerWidth < 768 ? 'col-12' : 'col-md-4';

                const card = document.createElement('div');
                card.className = 'card';

                const cardHeader = document.createElement('div');
                cardHeader.className = 'card-header';
                
                // Tách thành 2 button groups riêng biệt
                const priceButtonGroup = document.createElement('div');
                priceButtonGroup.className = 'd-flex flex-wrap gap-1 justify-content-center mb-2';

                const sortButtonGroup = document.createElement('div');
                sortButtonGroup.className = 'd-flex flex-wrap gap-1 justify-content-center';

                const priceButtons = [
                    { text: '↟ High', id: 'high' },
                    { text: '↡ Low', id: 'low' }
                ];

                const sortButtons = [
                    { text: '↑ Price', id: 'asc' },
                    { text: '↓ Price', id: 'desc' },
                    { text: '⌚ Time', id: 'time' }
                ];

                // Tạo các nút chọn giá
                priceButtons.forEach(btn => {
                    const button = document.createElement('button');
                    button.className = 'btn btn-sm btn-outline-primary price-button';
                    button.textContent = btn.text;
                    button.dataset.priceMode = btn.id;
                    if (btn.id === 'low') button.classList.add('active');
                    priceButtonGroup.appendChild(button);
                });

                // Tạo các nút sắp xếp
                sortButtons.forEach(btn => {
                    const button = document.createElement('button');
                    button.className = 'btn btn-sm btn-outline-primary sort-button';
                    button.textContent = btn.text;
                    button.dataset.sortType = btn.id;
                    if (btn.id === 'asc') button.classList.add('active');
                    sortButtonGroup.appendChild(button);
                });

                cardHeader.appendChild(priceButtonGroup);
                cardHeader.appendChild(sortButtonGroup);

                const cardBody = document.createElement('div');
                cardBody.className = 'card-body';

                const dateTitle = document.createElement('h6');
                dateTitle.className = 'card-title text-center mb-3';
                dateTitle.textContent = currentDate;

                const textarea = document.createElement('textarea');
                textarea.className = 'historical-textarea';
                textarea.setAttribute('readonly', true);

                const limitsContainer = document.createElement('div');
                limitsContainer.className = 'mt-1 limit-section';

                const ratioDisplay = document.createElement('p');
                const lowLimitDisplay = document.createElement('p');
                const highLimitDisplay = document.createElement('p');

                limitsContainer.appendChild(ratioDisplay);
                limitsContainer.appendChild(lowLimitDisplay);
                limitsContainer.appendChild(highLimitDisplay);

                // Data processing logic
                const formattedDayData = dayData.map(record => ({
                    time: record[0],
                    highPrice: parseFloat(record[2]),
                    lowPrice: parseFloat(record[3]),
                    displayHigh: `${record[0]} : ${parseFloat(record[2]).toFixed(8)}`,
                    displayLow: `${record[0]} : ${parseFloat(record[3]).toFixed(8)}`
                }));

                let currentPriceMode = 'low';
                let currentSortType = 'asc';

                const getCurrentPrice = (item) => currentPriceMode === 'high' ? item.highPrice : item.lowPrice;
                const getCurrentDisplay = (item) => currentPriceMode === 'high' ? item.displayHigh : item.displayLow;

                const updateLimits = () => {
                    const lowestPrice = Math.min(...formattedDayData.map(item => item.lowPrice));
                    const highestPrice = Math.max(...formattedDayData.map(item => item.lowPrice));
                    const { lowLimit, highLimit } = calculateLimits(lowestPrice, highestPrice);
                    const ratio = (highestPrice / lowestPrice).toFixed(4);

                    ratioDisplay.innerHTML = `<b>Tỉ lệ Cao/Thấp: </b>${ratio}`;
                    lowLimitDisplay.innerHTML = `<b>Giới hạn Thấp: </b>${lowLimit}`;
                    highLimitDisplay.innerHTML = `<b>Giới hạn Cao: </b>${highLimit}`;
                };

                const updateTextarea = () => {
                    let sortedData = [...formattedDayData];
                    switch(currentSortType) {
                        case 'asc':
                            sortedData.sort((a, b) => getCurrentPrice(a) - getCurrentPrice(b));
                            break;
                        case 'desc':
                            sortedData.sort((a, b) => getCurrentPrice(b) - getCurrentPrice(a));
                            break;
                        case 'time':
                            break; // Giữ nguyên thứ tự thời gian
                    }
                    textarea.value = sortedData.map(item => getCurrentDisplay(item)).join('\n');
                    updateLimits();
                };

                // Add event listeners to price buttons
                priceButtonGroup.querySelectorAll('button').forEach(button => {
                    button.addEventListener('click', () => {
                        priceButtonGroup.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                        button.classList.add('active');
                        currentPriceMode = button.dataset.priceMode;
                        updateTextarea();
                    });
                });

                // Add event listeners to sort buttons
                sortButtonGroup.querySelectorAll('button').forEach(button => {
                    button.addEventListener('click', () => {
                        sortButtonGroup.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                        button.classList.add('active');
                        currentSortType = button.dataset.sortType;
                        updateTextarea();
                    });
                });

                // Initialize with default display
                updateTextarea();

                cardBody.appendChild(dateTitle);
                cardBody.appendChild(textarea);
                cardBody.appendChild(limitsContainer);
                card.appendChild(cardHeader);
                card.appendChild(cardBody);
                colDiv.appendChild(card);
                row.appendChild(colDiv);
            }
        }

        tableContainer.appendChild(row);
        container.appendChild(tableContainer);
    }
}


function calculateLimits(lowestPrice, highestPrice) {
    const ratio = highestPrice / lowestPrice;
    if (ratio < 1.05) {
        return { lowLimit: "Không", highLimit: "Không" };
    } else if (ratio < 1.08) {
        return { lowLimit: lowestPrice * 1.2, highLimit: highestPrice * 1.3 };
    } else if (ratio < 1.11) {
        return { lowLimit: lowestPrice * 2.2, highLimit: highestPrice * 2.3 };
    } else if (ratio < 1.15) {
        return { lowLimit: lowestPrice * 3.2, highLimit: highestPrice * 3.3 };
    }
    return { lowLimit: "Không", highLimit: "Không" };
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
