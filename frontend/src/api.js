const API_BASE_URL = "http://127.0.0.1:8000/api";

export async function loginPatient(email, password) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Login failed");
  }

  localStorage.setItem("access_token", data.access_token);

  return data;
}
export async function generateQueueQr(department, tokenNumber) {
  const token = localStorage.getItem("access_token");

  const response = await fetch(
    `${API_BASE_URL}/queue/${department}/${tokenNumber}/qr`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "QR generation failed");
  }

  return data;
}