document.addEventListener("DOMContentLoaded", function () {
    var copyButtons = document.querySelectorAll(".copy-btn");

    copyButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            var targetId = button.getAttribute("data-copy-target");
            var target = targetId ? document.getElementById(targetId) : null;
            if (!target) {
                return;
            }

            var text = (target.textContent || "").trim();
            if (!text) {
                return;
            }

            navigator.clipboard.writeText(text).then(function () {
                var original = button.textContent;
                button.textContent = "Copied";
                setTimeout(function () {
                    button.textContent = original;
                }, 1000);
            });
        });
    });
});
