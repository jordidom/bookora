document.addEventListener("DOMContentLoaded", () => {
  const flashes = document.querySelectorAll(".flash");
  if (flashes.length) {
    setTimeout(() => {
      flashes.forEach((flash) => {
        flash.style.transition = "0.4s ease";
        flash.style.opacity = "0";
        flash.style.transform = "translateY(-6px)";
        setTimeout(() => flash.remove(), 400);
      });
    }, 3500);
  }

  const coverInput = document.getElementById("portada");
  const previewImage = document.getElementById("coverPreview");
  const placeholder = document.getElementById("coverPlaceholder");

  if (coverInput && previewImage && placeholder) {
    coverInput.addEventListener("change", (event) => {
      const file = event.target.files[0];

      if (!file) {
        return;
      }

      const reader = new FileReader();

      reader.onload = function (e) {
        previewImage.src = e.target.result;
        previewImage.classList.remove("hidden");
        placeholder.classList.add("hidden");
      };

      reader.readAsDataURL(file);
    });
  }
});