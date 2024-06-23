document.addEventListener('DOMContentLoaded', function() {
    const tradeForm = document.getElementById('tradeForm');
    const tradeResult = document.getElementById('tradeResult');

    tradeForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const tradingPair = document.getElementById('tradingPair').value.toUpperCase() || 'ETHUSDT';
        const stopLoss = document.getElementById('stopLoss').value;
        const takeProfit = document.getElementById('takeProfit').value;
        const amountToRisk = document.getElementById('amountToRisk').value;
        const chainWinners = document.getElementById('chainWinners').checked;

        try {
            const response = await fetch('/trade', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    trading_pair: tradingPair,
                    stop_loss: parseFloat(stopLoss),
                    take_profit: parseFloat(takeProfit) || null,
                    amount_to_risk: parseFloat(amountToRisk),
                    chain_winners: chainWinners
                })
            });

            const result = await response.json();
            if (result.status === 'success') {
                tradeResult.innerHTML = `<p style="color: green;">${result.message}</p>`;
            } else {
                tradeResult.innerHTML = `<p style="color: red;">Error: ${result.message}</p>`;
            }
        } catch (error) {
            tradeResult.innerHTML = `<p style="color: red;">An error occurred: ${error.message}</p>`;
        }
    });
});