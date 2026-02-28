(function() {
  var qr = new QRCode(document.getElementById("qrcode"), {
    text: DEPOSIT_ADDR,
    width: 180,
    height: 180,
    colorDark: "#000000",
    colorLight: "#ffffff",
    correctLevel: QRCode.CorrectLevel.M
  });

  function pad(n) { return String(n).padStart(2, "0"); }

  function updateCountdown() {
    var now = new Date();
    var diff = Math.max(0, Math.floor((EXPIRES_AT - now) / 1000));
    var m = Math.floor(diff / 60);
    var s = diff % 60;
    var el = document.getElementById("countdown");
    el.textContent = pad(m) + ":" + pad(s);
    if (diff < 120) el.classList.add("urgent"); else el.classList.remove("urgent");
    if (diff === 0) el.textContent = "EXPIRED";
  }

  updateCountdown();
  setInterval(updateCountdown, 1000);

  document.querySelectorAll(".copy-btn").forEach(function(btn) {
    btn.addEventListener("click", function() {
      var text = btn.dataset.copy;
      navigator.clipboard.writeText(text).then(function() {
        btn.classList.add("copied");
        setTimeout(function() { btn.classList.remove("copied"); }, 1500);
      });
    });
  });

  var currentStatus = "pending";
  var terminal = ["completed", "expired", "failed"];

  function setStatus(status) {
    if (status === currentStatus) return;
    currentStatus = status;
    var dot = document.getElementById("statusDot");
    var text = document.getElementById("statusText");
    dot.className = "status-dot";
    if (status === "confirming") { dot.classList.add("confirming"); text.textContent = "Transaction detected, confirming\u2026"; }
    else if (status === "sweeping") { dot.classList.add("confirming"); text.textContent = "Transaction detected, confirming\u2026"; }
    else if (status === "completed") {
      dot.style.background = "var(--green)";
      dot.style.animation = "none";
      text.textContent = "Payment complete!";
      setTimeout(function() {
        document.getElementById("successOverlay").style.display = "flex";
      }, 800);
    }
    else if (status === "expired") { dot.classList.add("expired"); text.textContent = "Invoice expired"; }
  }

  var es = new EventSource(PP_BASE + "/pay/" + INVOICE_ID + "/stream");
  es.addEventListener("status", function(e) {
    var data = JSON.parse(e.data);
    setStatus(data.status);
    if (terminal.indexOf(data.status) !== -1) es.close();
  });
  es.onerror = function() {
    if (terminal.indexOf(currentStatus) !== -1) es.close();
  };
})();
