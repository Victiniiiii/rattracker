import { invoke } from "https://unpkg.com/@tauri-apps/api@2/core";
import { readTextFile, writeTextFile, BaseDirectory, exists } from "https://unpkg.com/@tauri-apps/api@2/fs";
import { Command } from "https://unpkg.com/@tauri-apps/api@2/shell";

const pythonBinary = "rat_tracker.exe"; // TODO: MAC/LINUX!!! IMPORT OS!!
const CONFIG_FILE = "config.json";

const filePathText = document.getElementById("filePath");
const runBtn = document.getElementById("runBtn");
const cancelBtn = document.getElementById("cancelBtn");
const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");
const form = document.getElementById("configForm");

document.addEventListener("DOMContentLoaded", async () => {
	let selectedFile = null;
	let pythonProcess = null;

	async function loadConfig() {
		try {
			const fileExists = await exists(CONFIG_FILE, { dir: BaseDirectory.App });
			if (fileExists) {
				const text = await readTextFile(CONFIG_FILE, { dir: BaseDirectory.App });
				return JSON.parse(text);
			}
		} catch (e) {
			console.warn("Error reading config.json, using defaults:", e);
		}

		return {
			mog2_history: 120,
			mog2_threshold: 40,
			mog2_detect_shadow: false,
			morph_open_k: 3,
			morph_close_k: 15,
			min_contour_area: 300,
			max_contour_area: 12000,
			trail_len: 40,
			debug_frames: 0,
			pool_radius_cm: 60,
			pool_west: null,
			pool_north: null,
			pool_east: null,
			pool_south: null,
		};
	}

	async function saveConfig(cfg) {
		try {
			await writeTextFile(CONFIG_FILE, JSON.stringify(cfg, null, 2), { dir: BaseDirectory.App });
			alert("Settings saved!");
		} catch (e) {
			console.error("Failed to save config:", e);
			alert("Error saving settings");
		}
	}

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

	const cfg = await loadConfig();
	for (const [key, value] of Object.entries(cfg)) {
		const input = form.elements[key];
		if (!input) continue;
		if (input.type === "checkbox") input.checked = value;
		else input.value = value;
	}

	form.onsubmit = async e => {
		e.preventDefault();
		const newCfg = {};
		for (const element of form.elements) {
			if (!element.name) continue;
			if (element.type === "checkbox") newCfg[element.name] = element.checked;
			else if (element.type === "number") newCfg[element.name] = Number(element.value);
			else newCfg[element.name] = element.value;
		}
		await saveConfig(newCfg);
	};

	runBtn.onclick = async () => {
		if (!selectedFile) return;
		runBtn.disabled = true;
		cancelBtn.disabled = false;

		progressBar.value = 0;
		progressText.textContent = "0%";

		pythonProcess = new Command(pythonBinary, ["--video", selectedFile]);

		pythonProcess.stdout.on("data", line => {
			const match = line.match(/(\d+(\.\d+)?)%/);
			if (match) {
				const pct = parseFloat(match[1]);
				progressBar.value = pct;
				progressText.textContent = `${pct.toFixed(1)}%`;
			}
		});

		pythonProcess.on("close", code => {
			console.log("Python process exited with code", code);
			runBtn.disabled = false;
			cancelBtn.disabled = true;
			progressBar.value = 100;
			progressText.textContent = "100%";
		});

		pythonProcess.spawn();
	};

	cancelBtn.onclick = () => {
		if (pythonProcess) {
			pythonProcess.kill();
			console.log("Process canceled by user");
			runBtn.disabled = false;
			cancelBtn.disabled = true;
			progressBar.value = 0;
			progressText.textContent = "0%";
		}
	};
});
