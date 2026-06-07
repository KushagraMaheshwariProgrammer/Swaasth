import googleServices from "../google-services.json";

const WEB_APP_ID = "1:384794855513:web:4dd4188fef420f1434c948";
const MEASUREMENT_ID = "G-CK6DZ9FQC9";

function getAndroidClient(clients) {
  return (
    clients.find((entry) => entry.client_info?.android_client_info?.package_name) ??
    clients[0]
  );
}

export function getFirebaseConfig() {
  const { project_info: projectInfo, client } = googleServices;

  if (!projectInfo?.project_id || !client?.length) {
    throw new Error("Invalid google-services.json: missing project_info or client.");
  }

  const androidClient = getAndroidClient(client);
  const apiKey = androidClient.api_key?.[0]?.current_key;

  if (!apiKey) {
    throw new Error("Invalid google-services.json: missing api_key.");
  }

  const projectId = projectInfo.project_id;

  return {
    apiKey,
    authDomain: `${projectId}.firebaseapp.com`,
    projectId,
    storageBucket: projectInfo.storage_bucket,
    messagingSenderId: projectInfo.project_number,
    appId: import.meta.env.VITE_FIREBASE_APP_ID || WEB_APP_ID,
    measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || MEASUREMENT_ID,
  };
}

export function getAndroidPackageName() {
  const androidClient = getAndroidClient(googleServices.client);
  return androidClient.client_info?.android_client_info?.package_name ?? null;
}
