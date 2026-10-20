import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyB4vt67y6WhQARjSfFi31I4ya7zpvWzzo0",
  authDomain: "study-flow-87df9.firebaseapp.com",
  projectId: "study-flow-87df9",
  storageBucket: "study-flow-87df9.firebasestorage.app",
  messagingSenderId: "775111904604",
  appId: "1:775111904604:web:145d855e126b1f05b2c599",
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
