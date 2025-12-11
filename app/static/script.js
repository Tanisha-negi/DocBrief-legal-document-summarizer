// Drama Meter Animation
document.addEventListener("DOMContentLoaded", () => {
  const meter = document.querySelector(".drama-meter");
  if (meter) {
    meter.classList.add("animate-bounce");
  }
});

// Responsive Navbar
const hamburger = document.getElementById("hamburger");
const mobileMenu = document.getElementById("mobile-menu");
const iconOpen = document.getElementById("icon-open");
const iconClose = document.getElementById("icon-close");

hamburger.addEventListener("click", () => {
  const isOpen = hamburger.getAttribute("aria-expanded") === "true";

  if (!isOpen) {
    mobileMenu.style.display = "block";
    mobileMenu.getBoundingClientRect(); // force reflow
    mobileMenu.classList.remove("opacity-0", "-translate-y-2");
    mobileMenu.classList.add("opacity-100", "translate-y-0");

    iconOpen.classList.add("hidden");
    iconClose.classList.remove("hidden");
    hamburger.setAttribute("aria-expanded", "true");
  } else {
    mobileMenu.classList.remove("opacity-100", "translate-y-0");
    mobileMenu.classList.add("opacity-0", "-translate-y-2");

    iconOpen.classList.remove("hidden");
    iconClose.classList.add("hidden");
    hamburger.setAttribute("aria-expanded", "false");

    mobileMenu.addEventListener(
      "transitionend",
      () => {
        if (hamburger.getAttribute("aria-expanded") === "false") {
          mobileMenu.style.display = "none";
        }
      },
      { once: true }
    );
  }
});
// Hero Section
const fileUpload = document.getElementById("file-upload");
fileUpload.addEventListener("change", () => {
  if (fileUpload.files.length > 0) {
    alert(`Selected file: ${fileUpload.files[0].name}`);
  }
});

// FAQ section

function toggleFAQ(button) {
  const answer = button.nextElementSibling;
  const arrow = button.querySelector("svg");

  answer.classList.toggle("hidden");
  arrow.classList.toggle("rotate-180");
}
