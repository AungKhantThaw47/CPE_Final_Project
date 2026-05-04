document.addEventListener("DOMContentLoaded", function () {
    // Copy button functionality
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

    // Tab switching functionality
    var tabButtons = document.querySelectorAll(".tab-button");
    tabButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            var tabName = button.getAttribute("data-tab");
            
            // Remove active class from all buttons
            tabButtons.forEach(function (btn) {
                btn.classList.remove("active");
            });
            
            // Add active class to clicked button
            button.classList.add("active");
            
            // Hide all tab contents
            var allContents = document.querySelectorAll(".tab-content");
            allContents.forEach(function (content) {
                content.classList.remove("active");
            });
            
            // Show clicked tab content
            var activeContent = document.getElementById(tabName);
            if (activeContent) {
                activeContent.classList.add("active");
            }
        });
    });

    // Sidebar navigation: switch tabs and jump to a hash/date anchor
    var sidebarLinks = document.querySelectorAll(".nav-link[data-tab], .nav-sublink[data-tab]");
    sidebarLinks.forEach(function (link) {
        link.addEventListener("click", function (e) {
            e.preventDefault();

            var tabName = link.getAttribute("data-tab");
            var targetId = link.getAttribute("data-target");
            var target = targetId ? document.getElementById(targetId) : null;

            if (tabName) {
                var tabButton = document.querySelector('.tab-button[data-tab="' + tabName + '"]');
                if (tabButton && !tabButton.classList.contains("active")) {
                    tabButton.click();
                }
            }

            setTimeout(function () {
                if (target) {
                    target.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            }, 50);
        });
    });

    // Handle confirm/reject buttons with AJAX to move to next article
    var actionForms = document.querySelectorAll(".action-form");

    actionForms.forEach(function (form) {
        form.addEventListener("submit", function (e) {
            e.preventDefault();

            var action = form.getAttribute("action");
            var blobName = form.querySelector("input[name='blob_name']").value;
            var row = form.closest("tr");

            // Submit via AJAX
            fetch(action, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body: new URLSearchParams({blob_name: blobName})
            })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (data) {
                        throw new Error(data.error || "Request failed");
                    });
                }
                return response.json();
            })
            .then(function (data) {
                // Remove the row from the table
                if (row) {
                    row.style.opacity = "0.5";
                    setTimeout(function () {
                        row.remove();
                        
                        // If there are more rows in this table, highlight the next one
                        var table = row.closest("table");
                        if (table) {
                            var nextRow = table.querySelector("tbody tr");
                            if (nextRow) {
                                nextRow.scrollIntoView({behavior: "smooth", block: "center"});
                                nextRow.style.backgroundColor = "#fff3cd";
                                setTimeout(function () {
                                    nextRow.style.backgroundColor = "";
                                }, 1500);
                            }
                        }
                    }, 300);
                }
            })
            .catch(function (error) {
                alert("Error: " + error.message);
            });
        });
    });
});
