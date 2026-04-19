## Todo List

- Make the top of the settings window fixed. So doesnt get lost while scrolling.
- Some hiccups on translations. (rat)
- Maybe make everything one row on top of the settings
- In settings rows try to make everything flex, possibly one row but extend if needed
- Exporting a profile should add the profile name in the arguments. And importing a new profile should create one, not change the current one.

- video preview feature. see how it looks before running the whole thing. Maybe pick the rat in a tool, then it auto adjusts some stuff.
- Batch processing videos
- Heatmap sigma exposed, the gaussian blur sigma is hardcoded at 20 in heatmap(). Depending on video resolution this can look very over or under-smoothed. Easy setting to add.
- stderr surfaced in UI, right now stderr goes only to console.error. If the Python binary crashes or throws an exception, the user just sees the UI hang until the process closes with a non-zero code. Showing stderr in a collapsible error panel would make debugging much easier for researchers who aren't developers.
Non-zero exit code handling, pythonProcess.on("close", code => ...) just calls setUIRunning(false) regardless of code. A failed run looks identical to a cancelled one.
- Multi-day comparaison, data comparaison between trials, make all the statistics inside the app.

- Set up Git and separate main.py to chunks?
- app icon (multiple), app name, app author name