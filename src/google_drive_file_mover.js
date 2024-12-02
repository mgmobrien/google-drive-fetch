function sortMeetingTranscripts() {
  try {
    const DRAGON_FOLDER_ID = "1FsPM-xB7EH6Fc2CCu67EHDhYMotx0EYc";
    const NO_INSTRUCTIONS_FOLDER_ID = "1EiScFFGiE6hdKBOZeSicnO_lxv2U3mcB";
    const CUSTOMER_FOLDER_ID = "108_9MeB539PK6NVEjgARZuQKfms_PPt0";
    const CATCHALL_FOLDER_ID = "1FD_UfXJ1gjOmFrjudnuMfrQ15On2JsMS";
    const MEET_RECORDINGS_DEFAULT_ID = "1vDeoPMKl9ca7HCudyFMKP89GK8V4RqWP";

    console.log("Starting script...");

    const query = `'${MEET_RECORDINGS_DEFAULT_ID}' in parents and (title contains 'Transcript' or title contains 'Recording')`;

    console.log("Using query: " + query);

    let files;
    try {
      files = DriveApp.searchFiles(query);
    } catch (e) {
      console.error("Failed to search Drive files:", e.message);
      return;
    }

    let fileCount = 0;
    let errorCount = 0;

    while (files.hasNext()) {
      try {
        const file = files.next();
        const fileName = file.getName();

        console.log("Processing file:", fileName);

        try {
          if (fileName.startsWith("Dragon & Matt")) {
            console.log("Moving Dragon file: " + fileName);
            file.moveTo(DriveApp.getFolderById(DRAGON_FOLDER_ID));
            fileCount++;
          } else if (fileName.startsWith("[No]")) {
            console.log("Moving No Instructions file: " + fileName);
            file.moveTo(DriveApp.getFolderById(NO_INSTRUCTIONS_FOLDER_ID));
            fileCount++;
          } else if (fileName.startsWith("[R]")) {
            console.log("Moving Customer Call file: " + fileName);
            file.moveTo(DriveApp.getFolderById(CUSTOMER_FOLDER_ID));
            fileCount++;
          } else {
            console.log("Moving to catch-all: " + fileName);
            file.moveTo(DriveApp.getFolderById(CATCHALL_FOLDER_ID));
            fileCount++;
          }
        } catch (moveError) {
          console.error(`Failed to move file ${fileName}:`, moveError.message);
          errorCount++;
          continue;
        }
      } catch (fileError) {
        console.error("Error processing file:", fileError.message);
        errorCount++;
        continue;
      }
    }

    console.log(`Completed: ${fileCount} files moved, ${errorCount} errors`);

    if (errorCount > 0) {
      console.warn(`Warning: ${errorCount} files failed to process`);
    }
  } catch (e) {
    console.error("Critical error in script:", e.message);
    throw e;
  }
}

function createJWT() {
  const header = {
    alg: "RS256",
    typ: "JWT",
  };

  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iat: now,
    exp: now + 10 * 60,
    iss: PropertiesService.getScriptProperties().getProperty("GITHUB_APP_ID"),
  };

  const privateKey =
    PropertiesService.getScriptProperties().getProperty("GITHUB_PRIVATE_KEY");

  console.log("App ID:", payload.iss);
  console.log("Private key starts with:", privateKey.substring(0, 50));
}
