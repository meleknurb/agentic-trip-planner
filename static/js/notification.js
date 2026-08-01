// static/js/notification.js

/**
 * @param {string} message 
 * @param {string} type 
 */
export function showNotification(message, type = "success") {
    console.log(`showNotification called: Message="${message}", Type="${type}"`);
    const notificationContainer = document.getElementById("notificationContainer");
    if (!notificationContainer) {
        console.error("No notification container found! Notification will not be displayed.");
        return;
    }

    const notification = document.createElement("div");
    notification.classList.add("notification-message");
    if (type === "error") {
        notification.classList.add("error");
    } else if (type === "success") {
        notification.classList.add("success");
    }
    notification.textContent = message;

    notificationContainer.appendChild(notification);
    console.log("Notification element appended to container:", notification); 


    setTimeout(() => {
        notification.remove();
        console.log("Notification removed:", message);
    }, 3500);
}