// Mobile navigation: class names must match the shared header in templates/base.html.
const menuToggle = document.querySelector(".menu-toggle");
const navLinks = document.querySelector(".nav-links");
const menuLinks = document.querySelector(".nav-links a");

if (menuToggle && navLinks) {
    menuToggle.addEventListener("click", () => {
        const open = navLinks.classList.toggle("open");
        menuToggle.setAttribute("aria-expanded", open);
    });

    // Close the menu after a visitor selects a page on a small screen.
    navLinks.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", () => navLinks.classList.remove("open"));
    });
}
// Keeps the shared footer copyright year current without editing the template annually.
const year = document.getElementById("year");
if (year) year.textContent = new Date().getFullYear();
