import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useNavigate } from "react-router-dom";

import AppNav from "../components/AppNav";

import {
  createAdminStaffUser,
  deleteAdminUser,
  getAdminQueue,
  getAdminUsers,
  getBackendHealth,
  getDatabaseHealth,
  updateDoctorShift,
} from "../api";

import "./AdminDashboard.css";

const COMMON_DEPARTMENTS = [
  "General Medicine",
  "Cardiology",
  "Pediatrics",
  "Orthopedics",
  "Emergency",
  "Dermatology",
  "ENT",
  "Ophthalmology",
  "Neurology",
  "Oncology",
];

export default function AdminDashboard() {
  const navigate = useNavigate();

  const [activeModule, setActiveModule] = useState("overview");
  const [users, setUsers] = useState([]);
  const [queue, setQueue] = useState([]);
  const [backendHealth, setBackendHealth] = useState(null);
  const [databaseHealth, setDatabaseHealth] = useState(null);

  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [loadingSystem, setLoadingSystem] = useState(false);
  const [savingUser, setSavingUser] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [userSearch, setUserSearch] = useState("");
  const [userRoleFilter, setUserRoleFilter] = useState("all");

  const [queueDepartmentFilter, setQueueDepartmentFilter] = useState("all");
  const [queueStatusFilter, setQueueStatusFilter] = useState("all");

  const [showCreateUser, setShowCreateUser] = useState(false);
  const [newUser, setNewUser] = useState({
    name: "",
    email: "",
    password: "",
    role: "doctor",
    department: "General Medicine",
    shift_start: "09:00",
    shift_end: "17:00",
    on_duty: true,
    queue_capacity: 25,
  });

  // Doctor shift editing state
  const [editingDoctorShift, setEditingDoctorShift] = useState(null);
  const [shiftForm, setShiftForm] = useState({
    shift_start: "09:00",
    shift_end: "17:00",
    on_duty: true,
    queue_capacity: 25,
  });
  const [savingShift, setSavingShift] = useState(false);

  // Staff deletion state
  const [staffToDelete, setStaffToDelete] = useState(null);
  const [deletingStaff, setDeletingStaff] = useState(false);

  // Autoscroll & highlight state
  const [highlightedUserEmail, setHighlightedUserEmail] = useState(null);
  const usersTableRef = useRef(null);
  const userRowRefs = useRef({});
  const moduleSectionRef = useRef(null);

  // Role check
  useEffect(() => {
    const role = sessionStorage.getItem("user_role");
    if (role !== "admin") {
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  function clearMessages() {
    setError("");
    setSuccess("");
  }

  // Load Users
  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    setError("");
    try {
      const data = await getAdminUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (requestError) {
      setError(requestError?.message || "Unable to load users.");
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  // Load Queue
  const loadQueue = useCallback(async () => {
    setLoadingQueue(true);
    setError("");
    try {
      const data = await getAdminQueue();
      setQueue(Array.isArray(data) ? data : []);
    } catch (requestError) {
      setError(requestError?.message || "Unable to load queues.");
    } finally {
      setLoadingQueue(false);
    }
  }, []);

  // Load System Status
  const loadSystemStatus = useCallback(async () => {
    setLoadingSystem(true);
    setError("");
    try {
      const results = await Promise.allSettled([
        getBackendHealth(),
        getDatabaseHealth(),
      ]);
      setBackendHealth(results[0].status === "fulfilled" ? results[0].value : null);
      setDatabaseHealth(results[1].status === "fulfilled" ? results[1].value : null);
      if (results.every((r) => r.status === "rejected")) {
        throw new Error("Unable to check system health.");
      }
    } catch (requestError) {
      setError(requestError?.message || "Unable to check system status.");
    } finally {
      setLoadingSystem(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
    loadQueue();
    loadSystemStatus();
  }, [loadUsers, loadQueue, loadSystemStatus]);

  async function refreshDashboard() {
    clearMessages();
    await Promise.all([loadUsers(), loadQueue(), loadSystemStatus()]);
    setSuccess("Administration data refreshed.");
  }

  // Smooth scroll and highlight helper
  function scrollToUserRow(email) {
    if (!email) return;
    setHighlightedUserEmail(email);
    setTimeout(() => {
      const rowElem = userRowRefs.current[email];
      if (rowElem) {
        rowElem.scrollIntoView({ behavior: "smooth", block: "center" });
      } else if (usersTableRef.current) {
        usersTableRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 150);

    // Clear highlight after 3 seconds
    setTimeout(() => {
      setHighlightedUserEmail((curr) => (curr === email ? null : curr));
    }, 3000);
  }

  // Quick Open Modal Helpers
  function openAddDoctor() {
    clearMessages();
    setNewUser({
      name: "",
      email: "",
      password: "",
      role: "doctor",
      department: "General Medicine",
      shift_start: "09:00",
      shift_end: "17:00",
      on_duty: true,
      queue_capacity: 25,
    });
    setShowCreateUser(true);
  }

  function openAddNurse() {
    clearMessages();
    setNewUser({
      name: "",
      email: "",
      password: "",
      role: "nurse",
      department: "General Medicine",
      shift_start: "09:00",
      shift_end: "17:00",
      on_duty: true,
      queue_capacity: 25,
    });
    setShowCreateUser(true);
  }

  function openAddReception() {
    clearMessages();
    setNewUser({
      name: "",
      email: "",
      password: "",
      role: "reception",
      department: "Hospital Front Desk",
      shift_start: "09:00",
      shift_end: "17:00",
      on_duty: true,
      queue_capacity: 25,
    });
    setShowCreateUser(true);
  }

  function openAddStaff() {
    clearMessages();
    setNewUser({
      name: "",
      email: "",
      password: "",
      role: "doctor",
      department: "General Medicine",
      shift_start: "09:00",
      shift_end: "17:00",
      on_duty: true,
      queue_capacity: 25,
    });
    setShowCreateUser(true);
  }

  // Create Staff
  async function handleCreateUser(event) {
    event.preventDefault();
    clearMessages();
    setSavingUser(true);

    try {
      const created = await createAdminStaffUser(
        newUser.email,
        newUser.password,
        newUser.role,
        newUser.name,
        newUser.department,
        newUser.shift_start,
        newUser.shift_end,
        newUser.on_duty,
        newUser.queue_capacity,
      );

      setUsers((current) => {
        const filtered = current.filter((u) => u.email.toLowerCase() !== created.email.toLowerCase());
        return [...filtered, created];
      });

      const roleName = created.role === "doctor"
        ? "Doctor"
        : created.role === "nurse"
        ? "Nurse"
        : created.role === "reception"
        ? "Receptionist"
        : created.role;

      setSuccess(`✓ Successfully registered ${roleName}: ${newUser.name ? `${newUser.name} (${created.email})` : created.email}!`);

      setShowCreateUser(false);
      setNewUser({
        name: "",
        email: "",
        password: "",
        role: "doctor",
        department: "General Medicine",
        shift_start: "09:00",
        shift_end: "17:00",
        on_duty: true,
        queue_capacity: 25,
      });

      // Switch to users module if not already there, and autoscroll to the new row
      setActiveModule("users");
      scrollToUserRow(created.email);
    } catch (requestError) {
      setError(requestError?.message || "Unable to create the staff account.");
    } finally {
      setSavingUser(false);
    }
  }

  // Open Shift Editor for a Doctor
  function openEditShift(doctorUser) {
    clearMessages();
    setEditingDoctorShift(doctorUser);
    setShiftForm({
      shift_start: doctorUser.shift_start || "09:00",
      shift_end: doctorUser.shift_end || "17:00",
      on_duty: doctorUser.on_duty !== false,
      queue_capacity: doctorUser.queue_capacity || 25,
    });
  }

  // Save Shift Changes
  async function handleSaveShift(event) {
    event.preventDefault();
    if (!editingDoctorShift) return;

    clearMessages();
    setSavingShift(true);

    try {
      const updated = await updateDoctorShift(editingDoctorShift.email, shiftForm);
      setUsers((current) =>
        current.map((u) =>
          u.email.toLowerCase() === updated.email.toLowerCase() ? { ...u, ...updated } : u,
        ),
      );
      setSuccess(`✓ Updated shift and duty status for Dr. ${updated.name || updated.email}!`);
      const targetEmail = editingDoctorShift.email;
      setEditingDoctorShift(null);
      scrollToUserRow(targetEmail);
    } catch (requestError) {
      setError(requestError?.message || "Unable to update doctor shift.");
    } finally {
      setSavingShift(false);
    }
  }

  // Confirm and Remove Staff
  function requestDeleteStaff(user) {
    clearMessages();
    setStaffToDelete(user);
  }

  async function handleConfirmDeleteStaff() {
    if (!staffToDelete) return;
    clearMessages();
    setDeletingStaff(true);

    try {
      await deleteAdminUser(staffToDelete.email);
      setUsers((current) =>
        current.filter((u) => u.email.toLowerCase() !== staffToDelete.email.toLowerCase()),
      );
      setSuccess(`✓ Successfully removed ${staffToDelete.role} account: ${staffToDelete.name ? `${staffToDelete.name} (${staffToDelete.email})` : staffToDelete.email}.`);
      setStaffToDelete(null);
    } catch (requestError) {
      setError(requestError?.message || "Unable to remove staff member.");
    } finally {
      setDeletingStaff(false);
    }
  }

  // User Counts
  const userCounts = useMemo(() => {
    const counts = {
      total: users.length,
      patient: 0,
      doctor: 0,
      nurse: 0,
      reception: 0,
      admin: 0,
    };

    users.forEach((user) => {
      const role = String(user?.role || "").toLowerCase();
      if (Object.prototype.hasOwnProperty.call(counts, role)) {
        counts[role] += 1;
      }
    });

    return counts;
  }, [users]);

  // Queue Counts
  const queueCounts = useMemo(() => {
    const activeStatuses = ["waiting", "called", "in_consultation"];
    return {
      total: queue.length,
      waiting: queue.filter((entry) => String(entry?.status || "").toLowerCase() === "waiting").length,
      active: queue.filter((entry) => activeStatuses.includes(String(entry?.status || "").toLowerCase())).length,
      completed: queue.filter((entry) => String(entry?.status || "").toLowerCase() === "completed").length,
    };
  }, [queue]);

  // Departments
  const departments = useMemo(() => {
    return [
      ...new Set(
        queue
          .map((entry) => entry?.department)
          .filter(Boolean),
      ),
    ].sort();
  }, [queue]);

  // Filtered Users
  const filteredUsers = useMemo(() => {
    const search = userSearch.trim().toLowerCase();
    return users.filter((user) => {
      const email = String(user?.email || "").toLowerCase();
      const name = String(user?.name || "").toLowerCase();
      const role = String(user?.role || "").toLowerCase();
      const dept = String(user?.department || "").toLowerCase();

      const matchesSearch =
        !search ||
        email.includes(search) ||
        name.includes(search) ||
        dept.includes(search);

      const matchesRole = userRoleFilter === "all" || role === userRoleFilter;
      return matchesSearch && matchesRole;
    });
  }, [users, userSearch, userRoleFilter]);

  // Filtered Queue
  const filteredQueue = useMemo(() => {
    return queue.filter((entry) => {
      const matchesDepartment =
        queueDepartmentFilter === "all" ||
        entry?.department === queueDepartmentFilter;

      const matchesStatus =
        queueStatusFilter === "all" ||
        String(entry?.status || "").toLowerCase() === queueStatusFilter;

      return matchesDepartment && matchesStatus;
    });
  }, [queue, queueDepartmentFilter, queueStatusFilter]);

  function getStatusClass(status) {
    switch (String(status || "").toLowerCase()) {
      case "waiting":
        return "status-waiting";
      case "called":
        return "status-called";
      case "in_consultation":
        return "status-in-consultation";
      case "completed":
        return "status-completed";
      case "skipped":
        return "status-skipped";
      default:
        return "status-unknown";
    }
  }

  function getRiskClass(level) {
    switch (String(level || "").toLowerCase()) {
      case "low":
        return "risk-low";
      case "medium":
        return "risk-medium";
      case "high":
        return "risk-high";
      case "urgent":
        return "risk-urgent";
      default:
        return "risk-unknown";
    }
  }

  function getHealthState(health) {
    if (!health) return "Service not responding";
    return String(health?.status || "operational").toUpperCase();
  }

  function openModule(module) {
    clearMessages();
    setActiveModule(module);
    setTimeout(() => {
      if (moduleSectionRef.current) {
        moduleSectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 60);
  }

  return (
    <main className="admin-dashboard">
      <AppNav />

      {/* ======================================================
          HERO & QUICK ACTIONS
          ====================================================== */}
      <section className="admin-hero">
        <div className="admin-hero-content">
          <p className="eyebrow">ADMIN DASHBOARD</p>
          <h1>System Administration</h1>
          <p className="admin-hero-description">
            Manage Care+ healthcare staff, add new doctors and nurses, monitor hospital queues, and oversee system health.
          </p>
        </div>

        <div className="admin-hero-actions">
          <button
            type="button"
            className="admin-refresh-button"
            onClick={refreshDashboard}
            disabled={loadingUsers || loadingQueue || loadingSystem}
            title="Refresh Data"
          >
            ↻ {loadingUsers || loadingQueue || loadingSystem ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </section>

      {/* ======================================================
          ALERTS
          ====================================================== */}
      {error && (
        <div className="admin-alert admin-alert-error">
          <strong>Error</strong>
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="admin-alert admin-alert-success">
          <strong>Success</strong>
          <span>{success}</span>
        </div>
      )}

      {/* ======================================================
          OVERVIEW SECTION
          ====================================================== */}
      <section className="admin-overview">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">OVERVIEW</p>
            <h2>Administration Center</h2>
          </div>
          <span className="admin-access-badge">Administrator Access</span>
        </div>

        {/* STAT CARDS */}
        <div className="admin-stat-grid">
          <button
            type="button"
            className="admin-stat-card"
            onClick={() => {
              setUserRoleFilter("all");
              openModule("users");
            }}
          >
            <span className="stat-icon">👥</span>
            <span className="stat-label">ALL USERS</span>
            <strong>{userCounts.total}</strong>
            <span className="stat-detail">{userCounts.patient} registered patients</span>
          </button>

          <button
            type="button"
            className="admin-stat-card stat-card-doctor"
            onClick={() => {
              setUserRoleFilter("doctor");
              openModule("users");
            }}
          >
            <span className="stat-icon">🩺</span>
            <span className="stat-label">DOCTORS</span>
            <strong>{userCounts.doctor}</strong>
            <span className="stat-detail">Active medical doctors</span>
          </button>

          <button
            type="button"
            className="admin-stat-card stat-card-nurse"
            onClick={() => {
              setUserRoleFilter("nurse");
              openModule("users");
            }}
          >
            <span className="stat-icon">👩‍⚕️</span>
            <span className="stat-label">NURSES</span>
            <strong>{userCounts.nurse}</strong>
            <span className="stat-detail">Triage assessment staff</span>
          </button>

          <button
            type="button"
            className="admin-stat-card"
            onClick={() => openModule("queue")}
          >
            <span className="stat-icon">📋</span>
            <span className="stat-label">ACTIVE QUEUE</span>
            <strong>{queueCounts.active}</strong>
            <span className="stat-detail">{queueCounts.waiting} waiting in line</span>
          </button>
        </div>

        {/* DEDICATED STAFF ONBOARDING BANNER */}
        <div className="admin-staff-quick-actions">
          <div className="quick-staff-card doctor-card">
            <div className="quick-staff-icon">🩺</div>
            <div className="quick-staff-info">
              <h3>Doctor Onboarding</h3>
              <p>Create a medical doctor account with shift schedules and department assignment for consultations.</p>
            </div>
            <button
              type="button"
              className="quick-add-btn doctor-btn"
              onClick={openAddDoctor}
            >
              + Add Doctor
            </button>
          </div>

          <div className="quick-staff-card nurse-card">
            <div className="quick-staff-icon">👩‍⚕️</div>
            <div className="quick-staff-info">
              <h3>Nurse Onboarding</h3>
              <p>Create a triage nurse account with permissions to record vital signs and assess patient priorities.</p>
            </div>
            <button
              type="button"
              className="quick-add-btn nurse-btn"
              onClick={openAddNurse}
            >
              + Add Nurse
            </button>
          </div>

          <div className="quick-staff-card reception-card">
            <div className="quick-staff-icon">📋</div>
            <div className="quick-staff-info">
              <h3>Reception Onboarding</h3>
              <p>Create front-desk receptionist credentials to check-in patients, scan QR codes, and manage walk-ins.</p>
            </div>
            <button
              type="button"
              className="quick-add-btn reception-btn"
              onClick={openAddReception}
            >
              + Add Reception
            </button>
          </div>
        </div>

        {/* MODULE NAVIGATION CARDS */}
        <div className="admin-card-grid">
          <button
            type="button"
            className={`admin-module-card ${activeModule === "users" ? "module-active" : ""}`}
            onClick={() => openModule("users")}
          >
            <span className="module-icon">👥</span>
            <span className="module-content">
              <span className="module-label">STAFF & USER MANAGEMENT</span>
              <h3>Manage Healthcare Staff</h3>
              <p>Add new doctors and nurses, inspect registered staff, and view access credentials.</p>
            </span>
            <span className="module-footer">
              <span>{userCounts.doctor} Doctors · {userCounts.nurse} Nurses</span>
              <span className="module-arrow">→</span>
            </span>
          </button>

          <button
            type="button"
            className={`admin-module-card ${activeModule === "queue" ? "module-active" : ""}`}
            onClick={() => openModule("queue")}
          >
            <span className="module-icon">📋</span>
            <span className="module-content">
              <span className="module-label">QUEUE MANAGEMENT</span>
              <h3>Monitor Queues</h3>
              <p>Live visibility into waiting, called, and completed consultations across all hospital departments.</p>
            </span>
            <span className="module-footer">
              <span>{queueCounts.total} total queue records</span>
              <span className="module-arrow">→</span>
            </span>
          </button>

          <button
            type="button"
            className={`admin-module-card ${activeModule === "system" ? "module-active" : ""}`}
            onClick={() => openModule("system")}
          >
            <span className="module-icon">⚡</span>
            <span className="module-content">
              <span className="module-label">SYSTEM MONITORING</span>
              <h3>System Health</h3>
              <p>Check FastAPI backend and MongoDB cluster connection states in real time.</p>
            </span>
            <span className="module-footer">
              <span>Backend & Database Online</span>
              <span className="module-arrow">→</span>
            </span>
          </button>

          <button
            type="button"
            className={`admin-module-card ${activeModule === "departments" ? "module-active" : ""}`}
            onClick={() => openModule("departments")}
          >
            <span className="module-icon">🏥</span>
            <span className="module-content">
              <span className="module-label">CLINICAL DEPARTMENTS</span>
              <h3>Hospital Departments</h3>
              <p>Review patient queue distributions and active workloads across specialty areas.</p>
            </span>
            <span className="module-footer">
              <span>{departments.length} active departments</span>
              <span className="module-arrow">→</span>
            </span>
          </button>
        </div>
      </section>

      {/* ======================================================
          ACTIVE MODULE CONTAINER (WITH AUTO-SCROLL TARGET)
          ====================================================== */}
      <div ref={moduleSectionRef} className="admin-active-module-anchor">
      {/* ======================================================
          USER & STAFF MANAGEMENT MODULE
          ====================================================== */}
      {activeModule === "users" && (
        <section className="admin-data-card">
          <div className="data-card-header">
            <div>
              <p className="eyebrow">STAFF & USER MANAGEMENT</p>
              <h2>Healthcare Staff & User Accounts</h2>
              <p>Register new doctors and nurses or view registered hospital users.</p>
            </div>

            <div className="staff-header-actions">
              <button
                type="button"
                className="admin-action-btn admin-btn-doctor"
                onClick={openAddDoctor}
              >
                + Add Doctor
              </button>

              <button
                type="button"
                className="admin-action-btn admin-btn-nurse"
                onClick={openAddNurse}
              >
                + Add Nurse
              </button>

              <button
                type="button"
                className="admin-action-btn admin-btn-reception"
                onClick={openAddReception}
              >
                + Add Reception
              </button>
            </div>
          </div>

          {/* ROLE FILTER PILLS */}
          <div className="admin-filter-pills">
            <button
              type="button"
              className={`filter-pill pill-doctor ${userRoleFilter === "doctor" ? "pill-active" : ""}`}
              onClick={() => setUserRoleFilter("doctor")}
            >
              🩺 Doctors ({userCounts.doctor})
            </button>
            <button
              type="button"
              className={`filter-pill pill-nurse ${userRoleFilter === "nurse" ? "pill-active" : ""}`}
              onClick={() => setUserRoleFilter("nurse")}
            >
              👩‍⚕️ Nurses ({userCounts.nurse})
            </button>
            <button
              type="button"
              className={`filter-pill ${userRoleFilter === "patient" ? "pill-active" : ""}`}
              onClick={() => setUserRoleFilter("patient")}
            >
              Patients ({userCounts.patient})
            </button>
            <button
              type="button"
              className={`filter-pill ${userRoleFilter === "reception" ? "pill-active" : ""}`}
              onClick={() => setUserRoleFilter("reception")}
            >
              Reception ({userCounts.reception})
            </button>
            <button
              type="button"
              className={`filter-pill ${userRoleFilter === "admin" ? "pill-active" : ""}`}
              onClick={() => setUserRoleFilter("admin")}
            >
              Admin ({userCounts.admin})
            </button>
          </div>

          <div className="data-toolbar">
            <input
              type="search"
              placeholder="Search by name, email, or department..."
              value={userSearch}
              onChange={(event) => setUserSearch(event.target.value)}
              className="admin-input"
            />
          </div>

          {loadingUsers ? (
            <div className="admin-loading">Loading users...</div>
          ) : filteredUsers.length === 0 ? (
            <div className="admin-empty">
              <p>No staff or users match the selected filters.</p>
              <div style={{ marginTop: "12px", display: "flex", gap: "10px", justifyContent: "center" }}>
                <button type="button" className="quick-add-btn doctor-btn" onClick={openAddDoctor}>
                  + Add Doctor
                </button>
                <button type="button" className="quick-add-btn nurse-btn" onClick={openAddNurse}>
                  + Add Nurse
                </button>
              </div>
            </div>
          ) : (
              <div className="admin-table-wrapper" ref={usersTableRef}>
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Staff / User</th>
                      <th>Role</th>
                      <th>Department</th>
                      <th>Shift / Schedule</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((user, index) => {
                      const isDoctor = user.role === "doctor";
                      const isStaff = ["doctor", "nurse", "reception"].includes(user.role);
                      const isHighlighted = highlightedUserEmail === user.email;

                      return (
                        <tr
                          key={`${user.email}-${index}`}
                          ref={(el) => {
                            if (el) userRowRefs.current[user.email] = el;
                          }}
                          className={isHighlighted ? "row-highlight-active" : ""}
                        >
                          <td className="email-cell">
                            <div className="user-profile-cell">
                              <span className="user-avatar">
                                {user.role === "doctor" ? "🩺" : user.role === "nurse" ? "👩‍⚕️" : user.role === "admin" ? "🛡️" : user.role === "reception" ? "📋" : "👤"}
                              </span>
                              <div>
                                {user.name && <strong className="user-name-display">{user.name}</strong>}
                                <span className="user-email-display">{user.email}</span>
                              </div>
                            </div>
                          </td>

                          <td>
                            <span className={`role-badge role-${String(user.role || "").toLowerCase()}`}>
                              {String(user.role || "unknown").toUpperCase()}
                            </span>
                          </td>

                          <td className="department-cell">
                            {user.department || (isDoctor || user.role === "nurse" ? "General Medicine" : user.role === "reception" ? "Front Desk" : "—")}
                          </td>

                          <td>
                            {isDoctor ? (
                              <div className="shift-info-badge">
                                <span className={`shift-dot ${user.on_duty !== false ? "on-duty" : "off-duty"}`} />
                                <span>
                                  {user.shift_start || "09:00"} - {user.shift_end || "17:00"}
                                </span>
                                <small style={{ opacity: 0.8 }}>
                                  ({user.on_duty !== false ? "On Duty" : "Off Duty"})
                                </small>
                              </div>
                            ) : (
                              <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>—</span>
                            )}
                          </td>

                          <td>
                            <span className="active-status-pill">Active</span>
                          </td>

                          <td>
                            <div className="table-actions-cell">
                              {isDoctor && (
                                <button
                                  type="button"
                                  className="btn-action-edit-shift"
                                  onClick={() => openEditShift(user)}
                                  title="Change Doctor Shift Schedule"
                                >
                                  ⏰ Set Shift
                                </button>
                              )}

                              {isStaff ? (
                                <button
                                  type="button"
                                  className="btn-action-delete"
                                  onClick={() => requestDeleteStaff(user)}
                                  title={`Remove ${user.role} account`}
                                >
                                  🗑️ Remove
                                </button>
                              ) : (
                                <span style={{ color: "#94a3b8", fontSize: "0.8rem" }}>—</span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
          )}
        </section>
      )}

      {/* ======================================================
          QUEUE MONITOR MODULE
          ====================================================== */}
      {activeModule === "queue" && (
        <section className="admin-data-card">
          <div className="data-card-header">
            <div>
              <p className="eyebrow">QUEUE MANAGEMENT</p>
              <h2>Hospital Queue Monitor</h2>
              <p>Real-time queue visibility across all hospital departments.</p>
            </div>
            <span className="read-only-badge">Read Only</span>
          </div>

          <div className="queue-summary-grid">
            <div>
              <span>Total Entries</span>
              <strong>{queueCounts.total}</strong>
            </div>
            <div>
              <span>Waiting</span>
              <strong>{queueCounts.waiting}</strong>
            </div>
            <div>
              <span>Active Consultations</span>
              <strong>{queueCounts.active}</strong>
            </div>
            <div>
              <span>Completed</span>
              <strong>{queueCounts.completed}</strong>
            </div>
          </div>

          <div className="data-toolbar">
            <select
              value={queueDepartmentFilter}
              onChange={(event) => setQueueDepartmentFilter(event.target.value)}
              className="admin-select"
            >
              <option value="all">All departments</option>
              {departments.map((department) => (
                <option key={department} value={department}>
                  {department}
                </option>
              ))}
            </select>

            <select
              value={queueStatusFilter}
              onChange={(event) => setQueueStatusFilter(event.target.value)}
              className="admin-select"
            >
              <option value="all">All statuses</option>
              <option value="waiting">Waiting</option>
              <option value="called">Called</option>
              <option value="in_consultation">In consultation</option>
              <option value="completed">Completed</option>
              <option value="skipped">Skipped</option>
            </select>
          </div>

          {loadingQueue ? (
            <div className="admin-loading">Loading queues...</div>
          ) : filteredQueue.length === 0 ? (
            <div className="admin-empty">No queue entries match the selected filters.</div>
          ) : (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Token</th>
                    <th>Patient</th>
                    <th>Department</th>
                    <th>Assigned Doctor</th>
                    <th>Status</th>
                    <th>Estimated Wait</th>
                    <th>Priority Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredQueue.map((entry, index) => (
                    <tr key={`${entry.department}-${entry.token_number}-${index}`}>
                      <td>
                        <strong className="token-cell">
                          #{String(entry.token_number ?? "—").padStart(3, "0")}
                        </strong>
                      </td>
                      <td className="email-cell">{entry.patient_email || "—"}</td>
                      <td>{entry.department || "—"}</td>
                      <td>{entry.doctor_email || "—"}</td>
                      <td>
                        <span className={`status-badge ${getStatusClass(entry.status)}`}>
                          {String(entry.status || "Unknown").replaceAll("_", " ")}
                        </span>
                      </td>
                      <td>
                        {entry.predicted_wait_minutes != null
                          ? `${Number(entry.predicted_wait_minutes).toFixed(1)} min`
                          : "—"}
                      </td>
                      <td>
                        <span className={`risk-badge ${getRiskClass(entry.risk_level)}`}>
                          {entry.risk_level || "Unknown"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* ======================================================
          DEPARTMENTS OVERVIEW
          ====================================================== */}
      {activeModule === "departments" && (
        <section className="admin-data-card">
          <div className="data-card-header">
            <div>
              <p className="eyebrow">DEPARTMENT OVERVIEW</p>
              <h2>Hospital Departments</h2>
              <p>Clinical specialty areas with active patients and doctors.</p>
            </div>
            <span className="read-only-badge">Read Only</span>
          </div>

          {departments.length === 0 ? (
            <div className="admin-empty">No departments are currently represented in the queue.</div>
          ) : (
            <div className="department-grid">
              {departments.map((department) => {
                const departmentQueue = queue.filter((entry) => entry.department === department);
                const activeCount = departmentQueue.filter((entry) =>
                  ["waiting", "called", "in_consultation"].includes(String(entry.status || "").toLowerCase())
                ).length;

                return (
                  <article className="department-card" key={department}>
                    <div className="department-icon">🏥</div>
                    <div>
                      <p>DEPARTMENT</p>
                      <h3>{department}</h3>
                      <span>{departmentQueue.length} total patients in system</span>
                    </div>
                    <strong>
                      {activeCount} <small>active</small>
                    </strong>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* ======================================================
          SYSTEM HEALTH MODULE
          ====================================================== */}
      {activeModule === "system" && (
        <section className="admin-data-card">
          <div className="data-card-header">
            <div>
              <p className="eyebrow">SYSTEM MONITORING</p>
              <h2>System Health</h2>
              <p>Live status from Care+ backend and MongoDB services.</p>
            </div>
            <button
              type="button"
              className="admin-secondary-button"
              onClick={loadSystemStatus}
              disabled={loadingSystem}
            >
              {loadingSystem ? "Checking..." : "Check Again"}
            </button>
          </div>

          <div className="health-grid">
            <article className="health-card">
              <div className="health-card-top">
                <span className="health-icon">API</span>
                <span className={`health-status ${backendHealth ? "health-online" : "health-offline"}`}>
                  {backendHealth ? "Online" : "Unavailable"}
                </span>
              </div>
              <h3>Backend API</h3>
              <p>{getHealthState(backendHealth)}</p>
            </article>

            <article className="health-card">
              <div className="health-card-top">
                <span className="health-icon">DB</span>
                <span className={`health-status ${databaseHealth ? "health-online" : "health-offline"}`}>
                  {databaseHealth ? "Online" : "Unavailable"}
                </span>
              </div>
              <h3>MongoDB</h3>
              <p>{getHealthState(databaseHealth)}</p>
            </article>
          </div>
        </section>
      )}
      </div>

      {/* ======================================================
          MODAL: ADD NEW DOCTOR / NURSE / STAFF
          ====================================================== */}
      {showCreateUser && (
        <div
          className="admin-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setShowCreateUser(false);
            }
          }}
        >
          <div className="admin-modal">
            <div className="modal-header">
              <div>
                <p className="eyebrow">
                  {newUser.role === "doctor"
                    ? "DOCTOR ONBOARDING"
                    : newUser.role === "nurse"
                    ? "NURSE ONBOARDING"
                    : "STAFF ONBOARDING"}
                </p>
                <h2>
                  {newUser.role === "doctor"
                    ? "Add New Doctor"
                    : newUser.role === "nurse"
                    ? "Add New Nurse"
                    : "Create Staff Account"}
                </h2>
                <p>
                  {newUser.role === "doctor"
                    ? "Create credentials for a medical doctor to manage consultations and prescriptions."
                    : newUser.role === "nurse"
                    ? "Create credentials for a triage nurse to assess patient vitals and priority."
                    : "Set up login credentials and department assignment for hospital staff."}
                </p>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() => setShowCreateUser(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <form className="admin-form" onSubmit={handleCreateUser}>
              {/* FULL NAME */}
              <label>
                Full Name (Optional)
                <input
                  type="text"
                  value={newUser.name}
                  onChange={(event) =>
                    setNewUser((prev) => ({
                      ...prev,
                      name: event.target.value,
                    }))
                  }
                  placeholder={
                    newUser.role === "doctor"
                      ? "e.g. Dr. Sarah Miller, MD"
                      : newUser.role === "nurse"
                      ? "e.g. Nurse David Chen, RN"
                      : "Staff Full Name"
                  }
                />
              </label>

              {/* EMAIL */}
              <label>
                Staff Email (Login Username)
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(event) =>
                    setNewUser((prev) => ({
                      ...prev,
                      email: event.target.value,
                    }))
                  }
                  placeholder={
                    newUser.role === "doctor"
                      ? "doctor@careplus.com"
                      : newUser.role === "nurse"
                      ? "nurse@careplus.com"
                      : "staff@careplus.com"
                  }
                  required
                />
              </label>

              {/* PASSWORD */}
              <label>
                Account Password
                <input
                  type="password"
                  value={newUser.password}
                  onChange={(event) =>
                    setNewUser((prev) => ({
                      ...prev,
                      password: event.target.value,
                    }))
                  }
                  placeholder="Minimum 8 characters (e.g. Doctor@12345)"
                  minLength={8}
                  required
                />
              </label>

              {/* DEPARTMENT */}
              {(newUser.role === "doctor" || newUser.role === "nurse") && (
                <label>
                  Assigned Department
                  <select
                    value={newUser.department}
                    onChange={(event) =>
                      setNewUser((prev) => ({
                        ...prev,
                        department: event.target.value,
                      }))
                    }
                  >
                    {COMMON_DEPARTMENTS.map((dept) => (
                      <option key={dept} value={dept}>
                        {dept}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {/* DOCTOR SHIFT CONFIGURATION (WHEN DOCTOR SELECTED) */}
              {newUser.role === "doctor" && (
                <div style={{ marginTop: "10px", padding: "14px", background: "#f0fdfa", borderRadius: "12px", border: "1.5px solid #ccfbf1" }}>
                  <p style={{ margin: "0 0 10px", fontWeight: "800", color: "#0f766e", fontSize: "0.85rem" }}>
                    🩺 DOCTOR SHIFT & AVAILABILITY
                  </p>
                  <div className="shift-grid-row">
                    <label>
                      Shift Start
                      <input
                        type="time"
                        value={newUser.shift_start}
                        onChange={(event) =>
                          setNewUser((prev) => ({
                            ...prev,
                            shift_start: event.target.value,
                          }))
                        }
                        required
                      />
                    </label>
                    <label>
                      Shift End
                      <input
                        type="time"
                        value={newUser.shift_end}
                        onChange={(event) =>
                          setNewUser((prev) => ({
                            ...prev,
                            shift_end: event.target.value,
                          }))
                        }
                        required
                      />
                    </label>
                  </div>

                  <div className="shift-grid-row" style={{ marginTop: "10px" }}>
                    <label>
                      Queue Capacity
                      <input
                        type="number"
                        min="1"
                        max="200"
                        value={newUser.queue_capacity}
                        onChange={(event) =>
                          setNewUser((prev) => ({
                            ...prev,
                            queue_capacity: event.target.value,
                          }))
                        }
                        required
                      />
                    </label>

                    <label className="duty-toggle-label" style={{ alignSelf: "flex-end", marginBottom: "8px" }}>
                      <input
                        type="checkbox"
                        checked={newUser.on_duty}
                        onChange={(event) =>
                          setNewUser((prev) => ({
                            ...prev,
                            on_duty: event.target.checked,
                          }))
                        }
                      />
                      <span>Active / On Duty</span>
                    </label>
                  </div>
                </div>
              )}

              <div className="form-actions">
                <button
                  type="button"
                  className="admin-secondary-button"
                  onClick={() => setShowCreateUser(false)}
                  disabled={savingUser}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className={`admin-primary-button ${newUser.role === "doctor" ? "submit-doctor" : newUser.role === "nurse" ? "submit-nurse" : "submit-reception"}`}
                  disabled={savingUser}
                >
                  {savingUser
                    ? "Creating Account..."
                    : newUser.role === "doctor"
                    ? "✓ Register Doctor"
                    : newUser.role === "nurse"
                    ? "✓ Register Nurse"
                    : newUser.role === "reception"
                    ? "✓ Register Receptionist"
                    : "Create Staff Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================
          MODAL: EDIT DOCTOR SHIFT
          ====================================================== */}
      {editingDoctorShift && (
        <div
          className="admin-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setEditingDoctorShift(null);
            }
          }}
        >
          <div className="admin-modal">
            <div className="modal-header">
              <div>
                <p className="eyebrow">DOCTOR SHIFT MANAGEMENT</p>
                <h2>Set Shift for {editingDoctorShift.name || editingDoctorShift.email}</h2>
                <p>Adjust working hours, patient queue capacity, and daily on-duty status.</p>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() => setEditingDoctorShift(null)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <form className="admin-form" onSubmit={handleSaveShift}>
              <label>
                Doctor Account
                <input
                  type="text"
                  value={`${editingDoctorShift.name ? `${editingDoctorShift.name} — ` : ""}${editingDoctorShift.email}`}
                  disabled
                  style={{ background: "#f8fafc", color: "#64748b" }}
                />
              </label>

              <label>
                Department
                <input
                  type="text"
                  value={editingDoctorShift.department || "General Medicine"}
                  disabled
                  style={{ background: "#f8fafc", color: "#64748b" }}
                />
              </label>

              <div className="shift-grid-row">
                <label>
                  Shift Start Time
                  <input
                    type="time"
                    value={shiftForm.shift_start}
                    onChange={(e) =>
                      setShiftForm((prev) => ({
                        ...prev,
                        shift_start: e.target.value,
                      }))
                    }
                    required
                  />
                </label>

                <label>
                  Shift End Time
                  <input
                    type="time"
                    value={shiftForm.shift_end}
                    onChange={(e) =>
                      setShiftForm((prev) => ({
                        ...prev,
                        shift_end: e.target.value,
                      }))
                    }
                    required
                  />
                </label>
              </div>

              <div className="shift-grid-row" style={{ marginTop: "10px" }}>
                <label>
                  Queue Capacity (Max Patients)
                  <input
                    type="number"
                    min="1"
                    max="500"
                    value={shiftForm.queue_capacity}
                    onChange={(e) =>
                      setShiftForm((prev) => ({
                        ...prev,
                        queue_capacity: e.target.value,
                      }))
                    }
                    required
                  />
                </label>

                <label className="duty-toggle-label" style={{ alignSelf: "flex-end", marginBottom: "8px" }}>
                  <input
                    type="checkbox"
                    checked={shiftForm.on_duty}
                    onChange={(e) =>
                      setShiftForm((prev) => ({
                        ...prev,
                        on_duty: e.target.checked,
                      }))
                    }
                  />
                  <span>Currently On Duty</span>
                </label>
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  className="admin-secondary-button"
                  onClick={() => setEditingDoctorShift(null)}
                  disabled={savingShift}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="admin-primary-button submit-doctor"
                  disabled={savingShift}
                >
                  {savingShift ? "Saving Shift..." : "✓ Update Shift Schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================
          MODAL: REMOVE STAFF CONFIRMATION
          ====================================================== */}
      {staffToDelete && (
        <div
          className="admin-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setStaffToDelete(null);
            }
          }}
        >
          <div className="admin-modal" style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <div>
                <p className="eyebrow" style={{ color: "#e11d48" }}>CONFIRM DELETION</p>
                <h2 style={{ color: "#9f1239" }}>Remove Staff Account</h2>
                <p>Are you sure you want to permanently remove this healthcare staff member?</p>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() => setStaffToDelete(null)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div style={{ padding: "16px", background: "#fff1f2", borderRadius: "12px", border: "1px solid #fecdd3", margin: "16px 0" }}>
              <p style={{ margin: "0 0 6px", fontWeight: "800", color: "#881337" }}>
                Staff Member Details:
              </p>
              <p style={{ margin: "0 0 4px", fontSize: "0.9rem", color: "#9f1239" }}>
                <strong>Role:</strong> {String(staffToDelete.role).toUpperCase()}
              </p>
              {staffToDelete.name && (
                <p style={{ margin: "0 0 4px", fontSize: "0.9rem", color: "#9f1239" }}>
                  <strong>Name:</strong> {staffToDelete.name}
                </p>
              )}
              <p style={{ margin: 0, fontSize: "0.9rem", color: "#9f1239" }}>
                <strong>Email:</strong> {staffToDelete.email}
              </p>
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="admin-secondary-button"
                onClick={() => setStaffToDelete(null)}
                disabled={deletingStaff}
              >
                Cancel
              </button>

              <button
                type="button"
                className="admin-primary-button btn-danger-confirm"
                onClick={handleConfirmDeleteStaff}
                disabled={deletingStaff}
              >
                {deletingStaff ? "Removing..." : "🗑️ Yes, Remove Staff"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
