/**
 * InflatableModel — Shared frontend scripts
 * Handles: contact form, verification code, generate page upload UI
 */

// ── Contact Form ────────────────────────────────────────────────────────────
const contactForm = document.getElementById("contact-form");
if (contactForm) {
  contactForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = document.getElementById("form-error");
    const submitBtn = document.getElementById("submit-btn");
    const spinner = document.getElementById("submit-spinner");
    const successMsg = document.getElementById("success-message");

    errorEl.classList.add("hidden");
    errorEl.textContent = "";

    const payload = {
      name: document.getElementById("name").value.trim(),
      email: document.getElementById("email").value.trim(),
      whatsapp: document.getElementById("whatsapp").value.trim(),
      social: document.getElementById("social").value.trim(),
      company: document.getElementById("company").value.trim(),
    };

    submitBtn.disabled = true;
    spinner.classList.remove("hidden");

    try {
      const resp = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();

      if (data.ok) {
        contactForm.classList.add("hidden");
        successMsg.classList.remove("hidden");
      } else {
        errorEl.textContent = data.error || "Something went wrong.";
        errorEl.classList.remove("hidden");
      }
    } catch {
      errorEl.textContent = "Network error. Please try again.";
      errorEl.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
      spinner.classList.add("hidden");
    }
  });
}

// ── Verification Code Input ─────────────────────────────────────────────────
const codeInputs = document.querySelectorAll(".code-digit");
if (codeInputs.length > 0) {
  codeInputs.forEach((input, idx) => {
    input.addEventListener("input", () => {
      // Only allow digits
      input.value = input.value.replace(/\D/g, "");
      if (input.value && idx < codeInputs.length - 1) {
        codeInputs[idx + 1].focus();
      }
      checkCodeComplete();
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" && !input.value && idx > 0) {
        codeInputs[idx - 1].focus();
      }
    });
    input.addEventListener("paste", (e) => {
      e.preventDefault();
      const paste = (e.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 6);
      paste.split("").forEach((ch, i) => {
        if (codeInputs[i]) codeInputs[i].value = ch;
      });
      checkCodeComplete();
    });
  });

  function getCode() {
    return Array.from(codeInputs).map(inp => inp.value).join("");
  }

  function checkCodeComplete() {
    const btn = document.getElementById("verify-btn");
    if (btn) btn.disabled = getCode().length !== 6;
  }

  // Verify button
  const verifyBtn = document.getElementById("verify-btn");
  if (verifyBtn) {
    verifyBtn.disabled = true;
    verifyBtn.addEventListener("click", async () => {
      const code = getCode();
      if (code.length !== 6) return;

      const errorEl = document.getElementById("verify-error");
      const spinner = document.getElementById("verify-spinner");
      const successEl = document.getElementById("verify-success");
      const verifyCard = document.querySelector(".verify-card");

      errorEl.classList.add("hidden");
      verifyBtn.disabled = true;
      spinner.classList.remove("hidden");

      try {
        const resp = await fetch("/api/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code }),
        });
        const data = await resp.json();

        if (data.ok) {
          verifyCard.classList.add("hidden");
          successEl.classList.remove("hidden");
        } else {
          errorEl.textContent = data.error || "Verification failed.";
          errorEl.classList.remove("hidden");
          codeInputs.forEach(inp => inp.value = "");
          codeInputs[0].focus();
        }
      } catch {
        errorEl.textContent = "Network error. Please try again.";
        errorEl.classList.remove("hidden");
      } finally {
        verifyBtn.disabled = getCode().length !== 6;
        spinner.classList.add("hidden");
      }
    });
  }

  // Resend button
  const resendBtn = document.getElementById("resend-btn");
  if (resendBtn) {
    resendBtn.addEventListener("click", async () => {
      resendBtn.disabled = true;
      resendBtn.textContent = "Sending...";
      try {
        await fetch("/api/resend-code", { method: "POST" });
        resendBtn.textContent = "Code Resent!";
        setTimeout(() => {
          resendBtn.textContent = "Resend Code";
          resendBtn.disabled = false;
        }, 3000);
      } catch {
        resendBtn.textContent = "Resend Code";
        resendBtn.disabled = false;
      }
    });
  }
}

// ── Generate Page: Upload & Form ────────────────────────────────────────────
const uploadZone = document.getElementById("upload-zone");
const imageInput = document.getElementById("image-input");
const imagePreview = document.getElementById("image-preview");
const previewImg = document.getElementById("preview-img");
const removeImageBtn = document.getElementById("remove-image");
const generateBtn = document.getElementById("generate-btn");
const generateStatus = document.getElementById("generate-status");

if (uploadZone && imageInput) {
  // Click to open file picker
  uploadZone.addEventListener("click", () => imageInput.click());

  // Drag & drop
  uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });
  uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("dragover");
  });
  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];
    if (file) handleFile(file);
  });

  function handleFile(file) {
    if (!file.type.startsWith("image/")) {
      alert("Please select an image file.");
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      uploadZone.classList.add("hidden");
      imagePreview.classList.remove("hidden");
      if (generateBtn) generateBtn.disabled = false;
    };
    reader.readAsDataURL(file);
  }

  if (removeImageBtn) {
    removeImageBtn.addEventListener("click", () => {
      imageInput.value = "";
      previewImg.src = "";
      uploadZone.classList.remove("hidden");
      imagePreview.classList.add("hidden");
      if (generateBtn) generateBtn.disabled = true;
    });
  }

  // Generate button
  if (generateBtn) {
    let pollTimer = null;

    async function pollTaskStatus(taskId) {
      try {
        const resp = await fetch(`/api/task-status/${taskId}`);
        const data = await resp.json();

        if (data.status === "completed") {
          clearInterval(pollTimer);
          if (generateStatus) {
            generateStatus.textContent = "3D model generated successfully!";
            generateStatus.style.background = "#f0fdf4";
            generateStatus.style.color = "#22c55e";
          }
          if (data.model_urls?.glb) {
            window.dispatchEvent(new CustomEvent("model-ready", {
              detail: { modelUrl: data.model_urls.glb }
            }));
          }
          generateBtn.disabled = false;
          generateBtn.textContent = "Generate 3D Model";
        } else if (data.status === "failed") {
          clearInterval(pollTimer);
          if (generateStatus) {
            generateStatus.textContent = "3D generation failed. Please try again.";
            generateStatus.style.background = "#fef2f2";
            generateStatus.style.color = "#ef4444";
          }
          generateBtn.disabled = false;
          generateBtn.textContent = "Generate 3D Model";
        } else if (data.status === "running" || data.status === "in_progress") {
          if (generateStatus) {
            generateStatus.textContent = "Generating 3D model... (processing)";
          }
        } else {
          if (generateStatus) {
            generateStatus.textContent = "Waiting in queue...";
          }
        }
      } catch {
        // keep polling on network error
      }
    }

    generateBtn.addEventListener("click", async () => {
      const file = imageInput.files[0];
      const description = document.getElementById("description")?.value.trim() || "";

      if (!file && !description) {
        alert("Please upload a reference image or provide a description.");
        return;
      }

      generateBtn.disabled = true;
      generateBtn.textContent = "Submitting...";
      if (generateStatus) {
        generateStatus.classList.remove("hidden");
        generateStatus.style.background = "#eff6ff";
        generateStatus.style.color = "#3b82f6";
        generateStatus.textContent = "Uploading and submitting 3D generation task...";
      }

      const formData = new FormData();
      if (file) formData.append("image", file);
      if (description) formData.append("description", description);

      try {
        const resp = await fetch("/api/generate-3d", {
          method: "POST",
          body: formData,
        });
        const data = await resp.json();

        if (data.ok) {
          const taskId = data.task_id;
          if (generateStatus) {
            generateStatus.textContent = `Task created. Waiting for 3D generation...`;
          }
          // Start polling every 5 seconds
          pollTimer = setInterval(() => pollTaskStatus(taskId), 5000);
          pollTaskStatus(taskId); // immediate first check
        } else {
          if (generateStatus) {
            generateStatus.textContent = "Error: " + (data.error || "Unknown error");
            generateStatus.style.background = "#fef2f2";
            generateStatus.style.color = "#ef4444";
          }
          generateBtn.disabled = false;
          generateBtn.textContent = "Generate 3D Model";
        }
      } catch (err) {
        if (generateStatus) {
          generateStatus.textContent = "Network error. Please try again.";
          generateStatus.style.background = "#fef2f2";
          generateStatus.style.color = "#ef4444";
        }
        generateBtn.disabled = false;
        generateBtn.textContent = "Generate 3D Model";
      }
    });
  }
}