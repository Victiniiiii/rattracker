import { invoke } from "https://unpkg.com/@tauri-apps/api@2/core";

document.addEventListener("DOMContentLoaded", () => {
	let selectedFile = null;
	const filePathText = document.getElementById("filePath");
	const runBtn = document.getElementById("runBtn");

	document.getElementById("selectFile").onclick = async () => {
		try {
			selectedFile = await invoke("pick_file");
			if (selectedFile) {
				filePathText.textContent = selectedFile;
				runBtn.disabled = false;
			}
		} catch (e) {
			console.log("No file selected or error:", e);
		}
	};
});
