# Runtime Test Checklist

- [ ] Start app without GeForce NOW installed
- [ ] `.env` missing `CLIENT_ID` shows clear error and exits
- [ ] `.env` valid `CLIENT_ID` starts app
- [ ] Picker opens on startup
- [ ] Tray icon appears
- [ ] Tray Force Game opens/focuses picker
- [ ] Search works
- [ ] Card click forces game
- [ ] Double-click forces and hides/minimizes picker
- [ ] Stop Current Presence clears RPC/fake process
- [ ] Exit cleans fake process
- [ ] Steam cookie flow still works
- [ ] Sync Games still works
- [ ] No public "Discord Quest Mode" string remains
