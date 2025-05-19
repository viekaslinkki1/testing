let coinCount = parseInt(document.getElementById("coin-count").innerText);

function dropBall() {
    if (coinCount < 100) {
        alert("Not enough coins!");
        return;
    }

    coinCount -= 100;
    document.getElementById("coin-count").innerText = coinCount;

    // Simulate the ball drop with random physics
    const winnings = Math.random() > 0.5 ? 200 : 0; // 50% chance to double or lose
    
    fetch("/plinko", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ winnings: winnings })
    }).then(response => response.json()).then(data => {
        if (data.status === "success") {
            coinCount = data.new_balance;
            document.getElementById("coin-count").innerText = coinCount;
        } else {
            alert(data.message);
        }
    });
}
