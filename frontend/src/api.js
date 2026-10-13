// ============================================================
// API CONFIGURATION
// ============================================================

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000/api";


// ============================================================
// STORAGE KEYS
// ============================================================

const STORAGE_KEYS = {
  ACCESS_TOKEN: "access_token",
  USER_ROLE: "user_role",
  USER_EMAIL: "user_email",
};


// ============================================================
// AUTH HELPERS
// ============================================================

function getToken() {
  return sessionStorage.getItem(
    STORAGE_KEYS.ACCESS_TOKEN,
  );
}



function clearAuthStorage() {

  sessionStorage.removeItem(
    STORAGE_KEYS.ACCESS_TOKEN,
  );

  sessionStorage.removeItem(
    STORAGE_KEYS.USER_ROLE,
  );

  sessionStorage.removeItem(
    STORAGE_KEYS.USER_EMAIL,
  );

}


// ============================================================
// VALUE HELPERS
// ============================================================

function cleanString(value) {

  return String(
    value ?? "",
  ).trim();

}


function cleanEmail(email) {

  return cleanString(
    email,
  ).toLowerCase();

}


function requireValue(
  value,
  message,
) {

  const cleaned =
    cleanString(value);

  if (!cleaned) {

    throw new Error(
      message,
    );

  }

  return cleaned;

}


function encodeValue(value) {

  return encodeURIComponent(
    cleanString(value),
  );

}


// ============================================================
// GENERIC REQUEST
// ============================================================

async function request(
  path,
  options = {},
) {

  const token =
    getToken();


  const headers = {
    Accept:
      "application/json",

    ...(options.headers || {}),
  };


  // Only send Content-Type when a body exists.
  if (
    options.body !== undefined &&
    options.body !== null
  ) {

    headers["Content-Type"] =
      "application/json";

  }


  // Add JWT automatically.
  if (token) {

    headers.Authorization =
      `Bearer ${token}`;

  }


  let response;


  try {

    response =
      await fetch(
        `${API_BASE_URL}${path}`,
        {
          ...options,
          headers,
        },
      );

  } catch (networkError) {

    console.error(
      "API network error:",
      networkError,
    );

    throw new Error(
      "Unable to connect to the hospital backend.",
    );

  }


  // ==========================================================
  // READ RESPONSE
  // ==========================================================

  const text =
    await response.text();


  let data = {};


  if (text) {

    try {

      data =
        JSON.parse(
          text,
        );

    } catch {

      data = {
        detail:
          text,
      };

    }

  }


  // ==========================================================
  // HANDLE HTTP ERRORS
  // ==========================================================

  if (!response.ok) {

    let message =
      `Request failed (${response.status})`;


    const detail =
      data?.detail;


    // FastAPI string error
    if (
      typeof detail ===
      "string"
    ) {

      message =
        detail;

    }


    // FastAPI validation errors
    else if (
      Array.isArray(detail)
    ) {

      message =
        detail
          .map(
            (item) => {

              if (
                typeof item ===
                "string"
              ) {

                return item;

              }


              if (
                item?.msg
              ) {

                return item.msg;

              }


              return JSON.stringify(
                item,
              );

            },
          )
          .join(", ");

    }


    // Object error
    else if (
      detail &&
      typeof detail ===
        "object"
    ) {

      message =
        detail.msg ||
        detail.message ||
        JSON.stringify(
          detail,
        );

    }


    const error =
      new Error(
        message,
      );


    error.status =
      response.status;


    // Expired/invalid JWT.
    if (
      response.status ===
      401
    ) {

      clearAuthStorage();

    }


    throw error;

  }


  // ==========================================================
  // NO CONTENT
  // ==========================================================

  if (
    response.status ===
    204
  ) {

    return null;

  }


  return data;

}


// ============================================================
// AUTH - LOGIN
// ============================================================

export async function login(
  email,
  password,
) {

  const cleanUserEmail =
    cleanEmail(
      email,
    );


  if (!cleanUserEmail) {

    throw new Error(
      "Email is required.",
    );

  }


  if (!password) {

    throw new Error(
      "Password is required.",
    );

  }


  const data =
    await request(
      "/auth/login",
      {
        method:
          "POST",

        body:
          JSON.stringify({
            email:
              cleanUserEmail,

            password,
          }),
      },
    );


  if (
    !data?.access_token
  ) {

    throw new Error(
      "Login succeeded but no access token was returned.",
    );

  }


  sessionStorage.setItem(
    STORAGE_KEYS.ACCESS_TOKEN,
    data.access_token,
  );


  sessionStorage.setItem(
    STORAGE_KEYS.USER_ROLE,
    String(
      data.role || "",
    ).toLowerCase(),
  );


  sessionStorage.setItem(
    STORAGE_KEYS.USER_EMAIL,
    cleanUserEmail,
  );


  return data;

}


// ============================================================
// AUTH - GOOGLE LOGIN
// ============================================================

export async function loginWithGoogle(googleAccessToken) {
  const cleanToken = cleanString(googleAccessToken);

  if (!cleanToken) {
    throw new Error("Google authentication token is required.");
  }

  const data = await request("/auth/google", {
    method: "POST",
    body: JSON.stringify({
      access_token: cleanToken,
    }),
  });

  if (!data?.access_token) {
    throw new Error(
      "Google login succeeded but no Care+ access token was returned."
    );
  }

  sessionStorage.setItem(
    STORAGE_KEYS.ACCESS_TOKEN,
    data.access_token,
  );

  sessionStorage.setItem(
    STORAGE_KEYS.USER_ROLE,
    String(data.role || "").toLowerCase(),
  );

  sessionStorage.setItem(
    STORAGE_KEYS.USER_EMAIL,
    cleanEmail(data.email || ""),
  );

  return data;
}


// ============================================================
// AUTH - REGISTER PATIENT
// ============================================================

export async function registerPatient(
  email,
  password,
  phoneNumber = null,
  smsOptIn = false,
) {

  const cleanUserEmail =
    cleanEmail(
      email,
    );


  if (!cleanUserEmail) {

    throw new Error(
      "Email is required.",
    );

  }


  if (!password) {

    throw new Error(
      "Password is required.",
    );

  }

  const payload = {
    email: cleanUserEmail,
    password,
  };

  if (phoneNumber) {
    payload.phone_number = cleanString(phoneNumber);
  }
  if (smsOptIn) {
    payload.sms_opt_in = Boolean(smsOptIn);
  }

  return request(
    "/auth/register",
    {
      method:
        "POST",

      body:
        JSON.stringify(payload),
    },
  );

}


// ============================================================
// PATIENT - SMS NOTIFICATION PREFERENCES
// ============================================================

export async function getSmsPreferences() {
  return request("/patient/sms-preferences");
}

export async function updateSmsPreferences(preferences) {
  return request("/patient/sms-preferences", {
    method: "PUT",
    body: JSON.stringify({
      phone_number: preferences?.phone_number ? cleanString(preferences.phone_number) : null,
      sms_opt_in: Boolean(preferences?.sms_opt_in),
    }),
  });
}

// Aliases for compatibility
export const getWhatsAppPreferences = getSmsPreferences;
export const updateWhatsAppPreferences = updateSmsPreferences;

// ============================================================
// PATIENT - FCM PUSH NOTIFICATIONS
// ============================================================

export async function saveFcmToken(token, enabled = true) {
  return request("/patient/fcm-token", {
    method: "POST",
    body: JSON.stringify({
      fcm_token: cleanString(token),
      notifications_enabled: Boolean(enabled),
    }),
  });
}

export async function getFcmPreferences() {
  return request("/patient/fcm-preferences");
}


// ============================================================
// AUTH - CURRENT USER
// ============================================================

export async function getCurrentUser() {

  return request(
    "/auth/me",
  );

}


// ============================================================
// AUTH - LOGOUT
// ============================================================

export function logout() {

  clearAuthStorage();

}


// ============================================================
// PATIENT - MY QUEUE
// ============================================================

export async function getMyQueue() {
  try {
    return await request("/queue/my");
  } catch (error) {
    if (error?.status === 404) {
      return null;
    }

    throw error;
  }
}


// ============================================================
// PATIENT - JOIN QUEUE
// ============================================================

export async function joinQueue(
  department,
  doctorEmail,
) {

  const cleanDepartment =
    requireValue(
      department,
      "Department is required.",
    );


  const cleanDoctorEmail =
    cleanEmail(
      doctorEmail,
    );


  if (!cleanDoctorEmail) {

    throw new Error(
      "Please select a doctor.",
    );

  }


  return request(
    "/queue",
    {
      method:
        "POST",

      body:
        JSON.stringify({
          department:
            cleanDepartment,

          doctor_email:
            cleanDoctorEmail,
        }),
    },
  );

}


// ============================================================
// QUEUE - DEPARTMENT
// ============================================================

export async function getDepartmentQueue(
  department,
) {

  const cleanDepartment =
    requireValue(
      department,
      "Department is required.",
    );


  return request(
    `/queue/${encodeValue(
      cleanDepartment,
    )}`,
  );

}


// ============================================================
// RECEPTION QUEUE
// ============================================================

export async function getReceptionQueue(
  department,
) {

  const cleanDepartment = requireValue(
    department,
    "Department is required.",
  );

  return request(
    `/reception/queue/${encodeValue(
      cleanDepartment,
    )}`,
  );

}


// ============================================================
// PATIENT - PUBLIC QUEUE
// ============================================================

export async function getPublicDepartmentQueue(
  department,
) {

  const cleanDepartment =
    requireValue(
      department,
      "Department is required.",
    );


  return request(
    `/queue/${encodeValue(
      cleanDepartment,
    )}/public`,
  );

}


export async function getPublicDoctorQueue(
  department,
  doctorEmail,
) {

  const cleanDepartment = requireValue(
    department,
    "Department is required.",
  );

  const cleanDoctorEmail = requireValue(
    doctorEmail,
    "Doctor email is required.",
  );

  return request(
    `/queue/${encodeValue(
      cleanDepartment,
    )}/public/doctor/${encodeValue(
      cleanDoctorEmail,
    )}`,
  );

}


// ============================================================
// QUEUE - UPDATE STATUS
// ============================================================

export async function updateQueueStatus(
  department,
  tokenNumber,
  status,
) {

  const cleanDepartment =
    requireValue(
      department,
      "Department is required.",
    );


  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  const cleanStatus =
    requireValue(
      status,
      "Queue status is required.",
    );


  return request(
    `/queue/${encodeValue(
      cleanDepartment,
    )}/${encodeValue(
      token,
    )}/status`,
    {
      method:
        "PATCH",

      body:
        JSON.stringify({
          status:
            cleanStatus,
        }),
    },
  );

}


// ============================================================
// DOCTOR - DASHBOARD
// ============================================================

export async function getDoctorDashboard() {

  return request(
    "/doctor/dashboard",
  );

}


// ============================================================
// DOCTOR - GET PATIENT
// ============================================================

export async function getDoctorPatient(
  tokenNumber,
) {

  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  return request(
    `/doctor/patients/${encodeValue(
      token,
    )}`,
  );

}


// ============================================================
// DOCTOR - CALL PATIENT
//
// waiting → called
// ============================================================

export async function callDoctorPatient(
  tokenNumber,
) {

  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  return request(
    `/doctor/patients/${encodeValue(
      token,
    )}/call`,
    {
      method:
        "PATCH",
    },
  );

}


// ============================================================
// DOCTOR - START CONSULTATION
//
// called → in_consultation
// ============================================================

export async function startDoctorConsultation(
  tokenNumber,
) {

  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  return request(
    `/doctor/patients/${encodeValue(
      token,
    )}/start`,
    {
      method:
        "PATCH",
    },
  );

}


// ============================================================
// DOCTOR - GET CONSULTATION
//
// GET:
// /doctor/patients/{token}/consultation
// ============================================================

export async function getDoctorConsultation(
  tokenNumber,
) {

  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  return request(
    `/doctor/patients/${encodeValue(
      token,
    )}/consultation`,
  );

}


// ============================================================
// DOCTOR - SAVE CONSULTATION
//
// PUT:
// /doctor/patients/{token}/consultation
// ============================================================

export async function saveDoctorConsultation(
  tokenNumber,
  consultation,
) {

  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  if (
    !consultation ||
    typeof consultation !==
      "object"
  ) {

    throw new Error(
      "Consultation data is required.",
    );

  }


  const payload = {

    diagnosis:
      cleanString(
        consultation.diagnosis,
      ),

    consultation_notes:
      cleanString(
        consultation.consultation_notes,
      ),

    prescription:
      cleanString(
        consultation.prescription,
      ),

    treatment_advice:
      cleanString(
        consultation.treatment_advice,
      ),

  };


  return request(
    `/doctor/patients/${encodeValue(
      token,
    )}/consultation`,
    {
      method:
        "PUT",

      body:
        JSON.stringify(
          payload,
        ),
    },
  );

}


// ============================================================
// DOCTOR - COMPLETE CONSULTATION
//
// in_consultation → completed
// ============================================================

export async function completeDoctorConsultation(
  tokenNumber,
) {

  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  return request(
    `/doctor/patients/${encodeValue(
      token,
    )}/complete`,
    {
      method:
        "PATCH",
    },
  );

}


// ============================================================
// QUEUE - SKIP PATIENT
//
// active → skipped
// ============================================================

export async function skipPatient(
  department,
  tokenNumber,
) {

  const cleanDepartment =
    requireValue(
      department,
      "Department is required.",
    );


  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  return request(
    `/queue/${encodeValue(
      cleanDepartment,
    )}/${encodeValue(
      token,
    )}/skip`,
    {
      method:
        "PATCH",
    },
  );

}


// ============================================================
// QUEUE - REQUEUE PATIENT
//
// skipped → waiting
// ============================================================

export async function requeuePatient(
  department,
  tokenNumber,
) {

  const cleanDepartment =
    requireValue(
      department,
      "Department is required.",
    );


  const token =
    requireValue(
      tokenNumber,
      "Token number is required.",
    );


  return request(
    `/queue/${encodeValue(
      cleanDepartment,
    )}/${encodeValue(
      token,
    )}/requeue`,
    {
      method:
        "PATCH",
    },
  );

}


// ============================================================
// RECEPTION - GENERATE QUEUE QR
// ============================================================

export async function generateQueueQr(department, tokenNumber) {
  const cleanDepartment = requireValue(department, "Department is required.");
  const token = requireValue(tokenNumber, "Token number is required.");

  return request(
    `/queue/${encodeValue(cleanDepartment)}/${encodeValue(token)}/qr`,
    { method: "POST" },
  );
}


// ============================================================
// PATIENT - VERIFY RECEPTION QR
// ============================================================

export async function verifyQr(tokenOrOptions, manualCode = null) {
  let payload;

  // Existing QR scanner usage: verifyQr(scannedToken)
  if (
    typeof tokenOrOptions === "string" ||
    tokenOrOptions === null ||
    tokenOrOptions === undefined
  ) {
    const cleanToken = cleanString(tokenOrOptions);
    const cleanManualCode = cleanString(manualCode);

    if (!cleanToken && !cleanManualCode) {
      throw new Error(
        "QR token or 6-digit verification code is required."
      );
    }

    payload = cleanManualCode
      ? { manual_code: cleanManualCode }
      : { token: cleanToken };
  } else if (
    typeof tokenOrOptions === "object"
  ) {
    // Backup-code usage: verifyQr({ manual_code: "123456" })
    const cleanManualCode = cleanString(
      tokenOrOptions.manual_code
    );
    const cleanToken = cleanString(
      tokenOrOptions.token
    );

    if (!cleanToken && !cleanManualCode) {
      throw new Error(
        "QR token or 6-digit verification code is required."
      );
    }

    payload = cleanManualCode
      ? { manual_code: cleanManualCode }
      : { token: cleanToken };
  } else {
    throw new Error(
      "Invalid QR verification data."
    );
  }

  return request("/qr/verify", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ============================================================
// PATIENT - AVAILABLE DOCTORS
// ============================================================

export async function getAvailableDoctors(
  department,
) {

  const cleanDepartment =
    requireValue(
      department,
      "Department is required.",
    );


  return request(
    `/doctors/${encodeValue(
      cleanDepartment,
    )}`,
  );

}


// ============================================================
// NURSE - PATIENTS
// ============================================================

export async function getNursePatients() {

  return request(
    "/nurse/patients",
  );

}


// ============================================================
// NURSE - CREATE ASSESSMENT
// ============================================================

export async function createNurseAssessment(
  assessment,
) {

  if (
    !assessment ||
    typeof assessment !==
      "object"
  ) {

    throw new Error(
      "Assessment data is required.",
    );

  }


  return request(
    "/nurse/assessments",
    {
      method:
        "POST",

      body:
        JSON.stringify(
          assessment,
        ),
    },
  );

}


// ============================================================
// NURSE / DOCTOR - GET ASSESSMENT
// ============================================================

export async function getNurseAssessment(
  patientEmail,
) {

  const cleanPatientEmail =
    cleanEmail(
      patientEmail,
    );


  if (
    !cleanPatientEmail
  ) {

    throw new Error(
      "Patient email is required.",
    );

  }


  return request(
    `/nurse/assessments/${encodeValue(
      cleanPatientEmail,
    )}`,
  );

}


// ============================================================
// SYSTEM - HEALTH
// ============================================================

export async function getBackendHealth() {

  return request(
    "/health",
  );

}


// ============================================================
// SYSTEM - DATABASE HEALTH
// ============================================================

export async function getDatabaseHealth() {

  return request(
    "/db-health",
  );

}


// ============================================================
// ADMIN - LIST USERS
// ============================================================

export async function getAdminUsers() {
  return request("/admin/users");
}

// ============================================================
// ADMIN - CREATE STAFF USER
// Supported backend roles: doctor, nurse, reception
// ============================================================

export async function createAdminStaffUser(
  email,
  password,
  role,
  name = "",
  department = "",
  shiftStart = "09:00",
  shiftEnd = "17:00",
  onDuty = true,
  queueCapacity = 25,
) {
  const cleanUserEmail = cleanEmail(email);

  if (!cleanUserEmail) {
    throw new Error("Email is required.");
  }

  if (!password) {
    throw new Error("Password is required.");
  }

  if (password.length < 8) {
    throw new Error("Password must contain at least 8 characters.");
  }

  const cleanRole = cleanString(role).toLowerCase();

  if (!["doctor", "nurse", "reception"].includes(cleanRole)) {
    throw new Error("Please select a valid staff role.");
  }

  const payload = {
    email: cleanUserEmail,
    password,
    role: cleanRole,
  };

  const cleanName = cleanString(name);
  if (cleanName) {
    payload.name = cleanName;
  }

  const cleanDept = cleanString(department);
  if (cleanDept) {
    payload.department = cleanDept;
  }

  if (cleanRole === "doctor") {
    payload.shift_start = cleanString(shiftStart) || "09:00";
    payload.shift_end = cleanString(shiftEnd) || "17:00";
    payload.on_duty = Boolean(onDuty);

    const parsedCapacity = Number(queueCapacity);
    payload.queue_capacity = Number.isFinite(parsedCapacity) && parsedCapacity > 0
      ? Math.floor(parsedCapacity)
      : 25;
  }

  return request("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateDoctorShift(email, shiftData = {}) {
  const cleanUserEmail = cleanEmail(email);
  if (!cleanUserEmail) {
    throw new Error("Doctor email is required.");
  }

  const payload = {
    shift_start: cleanString(shiftData.shift_start) || "09:00",
    shift_end: cleanString(shiftData.shift_end) || "17:00",
    on_duty: Boolean(shiftData.on_duty),
    queue_capacity: Number.isFinite(Number(shiftData.queue_capacity)) && Number(shiftData.queue_capacity) > 0
      ? Math.floor(Number(shiftData.queue_capacity))
      : 25,
  };

  return request(`/admin/doctors/${encodeValue(cleanUserEmail)}/shift`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// ============================================================
// ADMIN - DELETE STAFF / USER
// ============================================================

export async function deleteAdminUser(email) {
  const cleanUserEmail = cleanEmail(email);
  if (!cleanUserEmail) {
    throw new Error("User email is required.");
  }

  return request(`/admin/users/${encodeValue(cleanUserEmail)}`, {
    method: "DELETE",
  });
}

// ============================================================
// ADMIN - VIEW ALL QUEUES (READ ONLY)
// ============================================================

export async function getAdminQueue() {
  return request("/admin/queue");
}



// ============================================================
// PAST MEDICAL RECORDS (READ ONLY)
// ============================================================

export async function getPatientMedicalHistory() {
  return request("/patient/medical-history");
}

export async function getNursePatientMedicalHistory(patientIdentifier) {
  const cleanIdentifier = requireValue(
    patientIdentifier,
    "Patient identifier is required.",
  );

  return request(
    `/nurse/patient/${encodeValue(cleanIdentifier)}/medical-history`,
  );
}

export async function getDoctorPatientMedicalHistory(patientIdentifier) {
  const cleanIdentifier = requireValue(
    patientIdentifier,
    "Patient identifier is required.",
  );

  return request(
    `/doctor/patient/${encodeValue(cleanIdentifier)}/medical-history`,
  );
}


// ============================================================
// DEFAULT EXPORT
// ============================================================

export default {

  // Authentication
  login,
  registerPatient,
  getCurrentUser,
  logout,

  // Patient
  getMyQueue,
  joinQueue,
  getPatientMedicalHistory,
  getSmsPreferences,
  updateSmsPreferences,
  getWhatsAppPreferences,
  updateWhatsAppPreferences,
  saveFcmToken,
  getFcmPreferences,

  // Queue
  getDepartmentQueue,
  getReceptionQueue,
  getPublicDepartmentQueue,
  getPublicDoctorQueue,
  updateQueueStatus,
  skipPatient,
  requeuePatient,

  // Doctor
  getDoctorDashboard,
  getDoctorPatient,
  callDoctorPatient,
  startDoctorConsultation,
  getDoctorConsultation,
  saveDoctorConsultation,
  completeDoctorConsultation,
  getDoctorPatientMedicalHistory,

  // Doctors
  getAvailableDoctors,

  // QR
  generateQueueQr,
  verifyQr,

  // Nurse
  getNursePatients,
  createNurseAssessment,
  getNurseAssessment,
  getNursePatientMedicalHistory,

  // System
  getBackendHealth,
  getDatabaseHealth,

  // Admin
  getAdminUsers,
  createAdminStaffUser,
  updateDoctorShift,
  deleteAdminUser,
  getAdminQueue,
};

