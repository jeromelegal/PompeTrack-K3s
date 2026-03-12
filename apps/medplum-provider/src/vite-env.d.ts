// SPDX-FileCopyrightText: Copyright Orangebot, Inc. and Medplum contributors
// SPDX-License-Identifier: Apache-2.0
/// <reference types="vite/client" />
interface Window {
  __APP_CONFIG__: {
    MEDPLUM_BASE_URL: string;
    MEDPLUM_CLIENT_ID: string;
  };
}