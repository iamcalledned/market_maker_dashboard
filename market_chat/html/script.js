document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');
    var loginButton = document.getElementById('login'); // Corrected ID to 'login'
    if (loginButton) {
        loginButton.addEventListener('click', function() {
            fetch('https://www.whattogrill.com/login', {
                method: 'GET' // or 'POST' if your endpoint expects a POST request
            })
            .then(response => {
                if (response.ok) {
                    console.log("Server woken up.");
                    // Handle successful response here, if needed
                } else {
                    console.error("Server responded with error status.");
                    // Handle error response here
                }
            })
            .catch(error => {
                console.error("Network error:", error);
                // Handle network error here
            });
        });
    } else {
        console.error('Login button not found.');
    }
});
