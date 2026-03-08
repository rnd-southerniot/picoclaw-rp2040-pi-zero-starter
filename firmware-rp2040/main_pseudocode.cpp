// Minimal RP2040 pseudocode scaffold for serial contract bring-up.

void setup() {
  init_wifi();
  init_tcp_server(8765);
  init_motors();
  init_encoders();
  init_imu();
  set_mode_safe();

  last_heartbeat_ms = now_ms();
  deadman_timeout_ms = 2000;
}

void loop() {
  read_sensors();
  process_json_lines_from_tcp();
  enforce_deadman();
  enforce_safety_limits();
  run_motion_control_if_enabled();
  publish_telemetry_periodically();
}

void process_json_lines_from_tcp() {
  ensure_tcp_client_connected();
  while (tcp_line_available()) {
    string line = tcp_readline();

    JsonObject msg;
    if (!parse_json_object(line, &msg)) {
      publish_error("invalid_json");
      continue;  // fail closed
    }

    string cmd = msg.get_string("cmd", "");

    if (cmd == "STOP") {
      stop_all_motion();
      set_mode_safe();
      publish_ack("STOP", true);
      continue;
    }

    if (cmd == "PING") {
      publish_ack("PING", true);
      continue;
    }

    if (cmd == "GET_STATE") {
      publish_state_snapshot();
      continue;
    }

    if (cmd == "HEARTBEAT") {
      last_heartbeat_ms = now_ms();
      publish_ack("HEARTBEAT", true);
      continue;
    }

    if (cmd == "TURN_TO") {
      if (!msg.has("heading")) {
        publish_error("missing_heading");
        continue;  // fail closed
      }
      set_turn_target_deg(msg.get_float("heading"));
      enable_heading_mode();
      publish_ack("TURN_TO", true);
      continue;
    }

    if (cmd == "DRIVE_DIST") {
      if (!msg.has("meters") || !msg.has("speed")) {
        publish_error("missing_drive_fields");
        continue;  // fail closed
      }
      start_distance_drive(msg.get_float("meters"), msg.get_float("speed"));
      publish_ack("DRIVE_DIST", true);
      continue;
    }

    publish_error("unsupported_cmd");
  }
}

void enforce_deadman() {
  if (motion_mode_enabled() && (now_ms() - last_heartbeat_ms) > deadman_timeout_ms) {
    stop_all_motion();
    set_mode_safe();
    publish_error("deadman_timeout");
  }
}
