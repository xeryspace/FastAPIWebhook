document.getElementById('tradeForm').addEventListener('submit', async function(event) {
    event.preventDefault();
    const stopLoss = document.getElementById('stopLoss').value;
    const takeProfit = document.getElementById('takeProfit').value;
    const amountToRisk = document.getElementById('amountToRisk').value;
    const chainWinners = document.getElementById('chainWinners').checked;
    const messageDiv = document.getElementById('message');

    try {
        const response = await fetch('/trade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stop_loss: parseFloat(stopLoss),
                take_profit: parseFloat(takeProfit) || null,
                amount_to_risk: parseFloat(amountToRisk),
                chain_winners: chainWinners
            })
        });

        const result = await response.json();
        messageDiv.textContent = result.message;
        messageDiv.style.color = result.status === 'success' ? 'green' : 'red';
    } catch (error) {
        messageDiv.textContent = 'An error occurred: ' + error.message;
        messageDiv.style.color = 'red';
    }
});