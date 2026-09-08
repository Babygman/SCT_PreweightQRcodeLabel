"""Central Thai/English UI text catalog.

English source text is used as the stable catalog key so existing tests and operator
terminology remain recognizable. Formatting always returns a plain string; Jinja keeps
its normal auto-escaping for every interpolated value.
"""

import re

TRANSLATIONS = {
    "Access denied": "ปฏิเสธการเข้าถึง",
    "Action": "การดำเนินการ",
    "Actions": "การดำเนินการ",
    "Active": "เปิดใช้งาน",
    "Actual": "ปริมาณจริง",
    "Actual Quantity": "ปริมาณจริง",
    "Actual Weight": "น้ำหนักจริง",
    "Administration & UAT Tools": "การดูแลระบบและเครื่องมือ UAT",
    "All": "ทั้งหมด",
    "All required weighings are complete": "การชั่งที่จำเป็นทั้งหมดเสร็จสมบูรณ์",
    "Apply": "นำไปใช้",
    "Back": "กลับ",
    "Back to Batch Details": "กลับไปยังรายละเอียดชุด",
    "Back to Home": "กลับหน้าหลัก",
    "Back to Master Data": "กลับไปยังข้อมูลหลัก",
    "Back to PO + Formula Scan": "กลับไปสแกน PO + สูตรการผลิต",
    "Back to Production Order Preparation": "กลับไปยังการเตรียมใบสั่งผลิต",
    "Back to Weighing": "กลับไปยังการชั่ง",
    "Batch": "ชุด",
    "Batch Number": "หมายเลขชุด",
    "Classification": "การจัดประเภท",
    "Code": "รหัส",
    "Batch details": "รายละเอียดชุด",
    "Block Common Exploits": "ป้องกันช่องโหว่ทั่วไป",
    "Cancel": "ยกเลิก",
    "Cancel This Weighing Session": "ยกเลิกเซสชันการชั่งนี้",
    "Cancel This Weighing Session?": "ยกเลิกเซสชันการชั่งนี้หรือไม่",
    "Category": "หมวดหมู่",
    "Child Tags": "ป้ายย่อย",
    "Comment": "หมายเหตุ",
    "Comment (optional)": "หมายเหตุ (ไม่บังคับ)",
    "Complete": "เสร็จสิ้น",
    "Complete Weighing Session": "เสร็จสิ้นเซสชันการชั่ง",
    "Complete Weighing Session?": "เสร็จสิ้นเซสชันการชั่งหรือไม่",
    "Completed": "เสร็จสมบูรณ์",
    "Completed Weighing Session": "เซสชันการชั่งที่เสร็จสมบูรณ์",
    "Display name": "ชื่อที่แสดง",
    "Completed at": "เสร็จสมบูรณ์เมื่อ",
    "Completed by": "เสร็จสมบูรณ์โดย",
    "Completed Production Orders": "ใบสั่งผลิตที่เสร็จสมบูรณ์",
    "Completion Summary": "สรุปการเสร็จสมบูรณ์",
    "Confirm": "ยืนยัน",
    "Confirm and Complete Session": "ยืนยันและเสร็จสิ้นเซสชัน",
    "Confirm Apply": "ยืนยันการนำไปใช้",
    "Confirm Issuance": "ยืนยันการออกป้าย",
    "Consumed": "ใช้งานแล้ว",
    "Continue": "ดำเนินการต่อ",
    "Continue Material Queue": "ดำเนินการคิววัตถุดิบต่อ",
    "Continue to Material Weighing": "ดำเนินการชั่งวัตถุดิบต่อ",
    "Create Another": "สร้างรายการอื่น",
    "Create Material Tag Batch": "สร้างชุดป้ายวัตถุดิบ",
    "Create Mock Production Documents": "สร้างเอกสารการผลิตจำลอง",
    "Create Preview": "สร้างตัวอย่าง",
    "Created": "สร้างเมื่อ",
    "Date": "วันที่",
    "Delivery Invoice": "ใบส่งสินค้า",
    "Draft expires": "แบบร่างหมดอายุ",
    "Error": "ข้อผิดพลาด",
    "Excel row": "แถว Excel",
    "Expected Finish Date": "วันที่คาดว่าจะผลิตเสร็จ",
    "Expected Finish Date must be on or after Production Date.": (
        "วันที่คาดว่าจะผลิตเสร็จต้องตรงกับหรือหลังวันที่ผลิต"
    ),
    "Expected Finish Date cannot be earlier than Production Date.": (
        "วันที่คาดว่าจะผลิตเสร็จต้องไม่ก่อนวันที่ผลิต"
    ),
    "Expiry Date": "วันที่หมดอายุ",
    "Expiry": "วันหมดอายุ",
    "Expired": "หมดอายุ",
    "Failed": "ล้มเหลว",
    "Formulas": "สูตรการผลิต",
    "Filter by status": "กรองตามสถานะ",
    "Finish Good": "สินค้าสำเร็จรูป",
    "Finish Goods Import": "การนำเข้าสินค้าสำเร็จรูป",
    "Finish Goods Master": "ข้อมูลหลักสินค้าสำเร็จรูป",
    "Finish Goods Master workbook": "ไฟล์ข้อมูลหลักสินค้าสำเร็จรูป",
    "Finished Good": "สินค้าสำเร็จรูป",
    "Finished Good Item Code": "รหัสสินค้าสำเร็จรูป",
    "Finished Good Name": "ชื่อสินค้าสำเร็จรูป",
    "Formula": "สูตรการผลิต",
    "Formula ID": "รหัสสูตรการผลิต",
    "Formula Items": "รายการสูตรการผลิต",
    "Formula Sheet": "เอกสารสูตรการผลิต",
    "Formula Sheet No.": "เลขที่เอกสารสูตรการผลิต",
    "Formula / PO-centric (Optional)": "การชั่งตามสูตร / PO (ทางเลือก)",
    "Full / Remainder / Total Tags": "เต็ม / คงเหลือ / ป้ายทั้งหมด",
    "Generated Mock Jobs": "งานจำลองที่สร้างแล้ว",
    "History": "ประวัติ",
    "Hold": "พักไว้",
    "Home": "หน้าหลัก",
    "Import": "นำเข้า",
    "Import Finish Goods Master": "นำเข้าข้อมูลหลักสินค้าสำเร็จรูป",
    "Import Material Master": "นำเข้าข้อมูลหลักวัตถุดิบ",
    "Inactive": "ปิดใช้งาน",
    "In progress": "อยู่ระหว่างดำเนินการ",
    "In Progress": "อยู่ระหว่างดำเนินการ",
    "Insert": "เพิ่ม",
    "Issued by": "ออกโดย",
    "Issued at": "ออกเมื่อ",
    "Issued": "ออกป้ายแล้ว",
    "Issued Material Tag Batch": "ชุดป้ายวัตถุดิบที่ออกแล้ว",
    "Issuer / Time": "ผู้ออก / เวลา",
    "Item Code": "รหัสรายการ",
    "Item Name": "ชื่อรายการ",
    "Keep Session": "คงเซสชันไว้",
    "Label": "ป้าย",
    "Large issuance": "การออกป้ายจำนวนมาก",
    "Line": "บรรทัด",
    "Location": "ตำแหน่ง",
    "Login": "เข้าสู่ระบบ",
    "Logout": "ออกจากระบบ",
    "Lot": "ล็อต",
    "Master Data": "ข้อมูลหลัก",
    "Material": "วัตถุดิบ",
    "Material Code": "รหัสวัตถุดิบ",
    "Material Code or Name": "รหัสหรือชื่อวัตถุดิบ",
    "Material Import": "การนำเข้าวัตถุดิบ",
    "Material Master workbook": "ไฟล์ข้อมูลหลักวัตถุดิบ",
    "Material Queue": "คิววัตถุดิบ",
    "Material Tag History": "ประวัติป้ายวัตถุดิบ",
    "Material Tag Issuance": "การออกป้ายวัตถุดิบ",
    "Material Tag Issuance History": "ประวัติการออกป้ายวัตถุดิบ",
    "Material Tag Issuance Preview": "ตัวอย่างการออกป้ายวัตถุดิบ",
    "Material Tag Batch {batch_number}": "ชุดป้ายวัตถุดิบ {batch_number}",
    "Material Tag Calibration": "การสอบเทียบป้ายวัตถุดิบ",
    "Material Tag Management": "การจัดการป้ายวัตถุดิบ",
    "Material Tag Print": "การพิมพ์ป้ายวัตถุดิบ",
    "Material Tag Print Preview": "ตัวอย่างการพิมพ์ป้ายวัตถุดิบ",
    "Material Tag Printer Calibration": "สอบเทียบเครื่องพิมพ์ป้ายวัตถุดิบ",
    "Material Tag QR": "QR ป้ายวัตถุดิบ",
    "Material-centric Preparation": "การเตรียมวัตถุดิบ",
    "Material-centric Weighing": "การชั่งตามวัตถุดิบ",
    "Mock Documents Ready": "เอกสารจำลองพร้อมแล้ว",
    "Mock ERP / Document Generator": "ERP จำลอง / เครื่องมือสร้างเอกสาร",
    "Mock ERP / Print QR Documents": "ERP จำลอง / พิมพ์เอกสาร QR",
    "Mock Documents {po}": "เอกสารจำลอง {po}",
    "Name": "ชื่อ",
    "Material Name": "ชื่อวัตถุดิบ",
    "Material capabilities": "ความสามารถด้านวัตถุดิบ",
    "Material ID": "รหัสวัตถุดิบ",
    "Materials": "วัตถุดิบ",
    "New Import": "นำเข้าใหม่",
    "Next": "ถัดไป",
    "No active Materials found.": "ไม่พบวัตถุดิบที่เปิดใช้งาน",
    "No active station is available.": "ไม่มีสถานีงานที่เปิดใช้งาน",
    "No data": "ไม่พบข้อมูล",
    "No data found": "ไม่พบข้อมูล",
    "No issued batches found.": "ไม่พบชุดที่ออกแล้ว",
    "No matching Active Finish Goods.": "ไม่พบสินค้าสำเร็จรูปที่เปิดใช้งานและตรงกัน",
    "No materials match this search and filter.": "ไม่มีวัตถุดิบตรงกับการค้นหาและตัวกรองนี้",
    "No mock jobs created yet.": "ยังไม่มีงานจำลองที่สร้าง",
    "None selected": "ยังไม่ได้เลือก",
    "Not rendered": "ยังไม่แสดงหน้าพิมพ์",
    "Original rendered": "แสดงหน้าพิมพ์ต้นฉบับแล้ว",
    "Pass": "ผ่าน",
    "Not started": "ยังไม่เริ่ม",
    "Open / Print Formula Sheet": "เปิด / พิมพ์เอกสารสูตรการผลิต",
    "Open / Print Production Order": "เปิด / พิมพ์ใบสั่งผลิต",
    "Only .xlsx workbooks are accepted.": "ยอมรับเฉพาะไฟล์ .xlsx",
    "Page": "หน้า",
    "Page {page} of {pages}": "หน้า {page} จาก {pages}",
    "Products": "ผลิตภัณฑ์",
    "QC": "การตรวจสอบคุณภาพ",
    "Raw Material Lots": "ล็อตวัตถุดิบ",
    "Page not found": "ไม่พบหน้า",
    "Password": "รหัสผ่าน",
    "Pending": "รอดำเนินการ",
    "Applied": "นำไปใช้แล้ว",
    "Cancelled": "ยกเลิกแล้ว",
    "Individual": "รายป้าย",
    "Open": "เปิด",
    "Original": "ต้นฉบับ",
    "Previewed": "ดูตัวอย่างแล้ว",
    "Ready": "พร้อม",
    "Rendered": "แสดงหน้าพิมพ์แล้ว",
    "Void": "ยกเลิกผล",
    "Voided": "ยกเลิกผลแล้ว",
    "Pending Material Tag validation": "รอตรวจสอบป้ายวัตถุดิบ",
    "PO": "PO",
    "PO Line": "บรรทัด PO",
    "Preweight ID": "รหัสชั่งล่วงหน้า",
    "Preview": "ดูตัวอย่าง",
    "Preweight Sticker {preweight_id}": "สติกเกอร์ชั่งล่วงหน้า {preweight_id}",
    "Please select a valid date from the calendar.": (
        "กรุณาเลือกวันที่ที่ถูกต้องจากปฏิทิน"
    ),
    "Open calendar for {field}": "เปิดปฏิทินสำหรับ {field}",
    "Previous": "ก่อนหน้า",
    "Print": "พิมพ์",
    "Print A4": "พิมพ์ A4",
    "Print Batch": "พิมพ์ชุด",
    "Print History": "ประวัติการพิมพ์",
    "Print status": "สถานะการพิมพ์",
    "Printer Calibration": "สอบเทียบเครื่องพิมพ์",
    "Product": "ผลิตภัณฑ์",
    "Production Date": "วันที่ผลิต",
    "Production Lot": "ล็อตการผลิต",
    "Production Lot No.": "เลขที่ล็อตการผลิต",
    "Production Order": "ใบสั่งผลิต",
    "Production Order No.": "เลขที่ใบสั่งผลิต",
    "Production Orders": "ใบสั่งผลิต",
    "Production Weighing": "การชั่งเพื่อการผลิต",
    "Purchase Order": "ใบสั่งซื้อ",
    "Quantity": "ปริมาณ",
    "Quantity to Produce (KG)": "ปริมาณที่ต้องผลิต (KG)",
    "Reason": "เหตุผล",
    "Received": "วันที่รับ",
    "Receiving Date": "วันที่รับ",
    "Receiving from": "วันที่รับตั้งแต่",
    "Receiving to": "วันที่รับถึง",
    "Receiving / Expiry": "วันที่รับ / วันหมดอายุ",
    "Reconciliation": "การกระทบยอด",
    "Recorded Actual Weight": "น้ำหนักจริงที่บันทึก",
    "Rejected": "ปฏิเสธ",
    "Reject": "ไม่ผ่าน",
    "Reprint": "พิมพ์ซ้ำ",
    "Reprint Tag {tag_number}": "พิมพ์ป้าย {tag_number} ซ้ำ",
    "Reprint Tag {tag_number} of {count}": "พิมพ์ป้าย {tag_number} จาก {count} ซ้ำ",
    "Reprints: {count}": "พิมพ์ซ้ำ: {count}",
    "Reprint Batch": "พิมพ์ชุดซ้ำ",
    "Reprint entire batch": "พิมพ์ทั้งชุดซ้ำ",
    "Reprint reason": "เหตุผลในการพิมพ์ซ้ำ",
    "Reprint reason must not contain control characters.": "เหตุผลในการพิมพ์ซ้ำต้องไม่มีอักขระควบคุม",
    "Render Reprint": "แสดงหน้าพิมพ์ซ้ำ",
    "Result": "ผลลัพธ์",
    "Return Home": "กลับหน้าหลัก",
    "Review Session": "ตรวจสอบเซสชัน",
    "Row": "แถว",
    "Save": "บันทึก",
    "Save Weighing": "บันทึกการชั่ง",
    "Scan Formula Sheet QR": "สแกน QR เอกสารสูตรการผลิต",
    "Scan Material Tag QR": "สแกน QR ป้ายวัตถุดิบ",
    "Scan Production Order": "สแกนใบสั่งผลิต",
    "Scan Production Order QR": "สแกน QR ใบสั่งผลิต",
    "Search": "ค้นหา",
    "Search and Select Finish Good": "ค้นหาและเลือกสินค้าสำเร็จรูป",
    "Search and Select Material": "ค้นหาและเลือกวัตถุดิบ",
    "Search code or description": "ค้นหารหัสหรือคำอธิบาย",
    "Select": "เลือก",
    "Select Material": "เลือกวัตถุดิบ",
    "Select a Finish Goods Master workbook.": "เลือกไฟล์ข้อมูลหลักสินค้าสำเร็จรูป",
    "Select a Material Master workbook.": "เลือกไฟล์ข้อมูลหลักวัตถุดิบ",
    "Select Station": "เลือกสถานีงาน",
    "Selected": "เลือกแล้ว",
    "Selected:": "เลือกแล้ว:",
    "Stations": "สถานีงาน",
    "Selected Finish Good": "สินค้าสำเร็จรูปที่เลือก",
    "Server error": "ข้อผิดพลาดของเซิร์ฟเวอร์",
    "Session ID": "รหัสเซสชัน",
    "Shelf": "ชั้นวาง",
    "Signed in as": "เข้าสู่ระบบในชื่อ",
    "Station": "สถานีงาน",
    "Standard Weight per Container": "น้ำหนักมาตรฐานต่อภาชนะ",
    "Status": "สถานะ",
    "Status / Weigh": "สถานะ / ชั่ง",
    "Success": "สำเร็จ",
    "Supplier": "ผู้จำหน่าย",
    "Tag": "ป้าย",
    "Tag count": "จำนวนป้าย",
    "Users": "ผู้ใช้งาน",
    "Tag {tag_number} of {count}": "ป้าย {tag_number} จาก {count}",
    "Tags": "ป้าย",
    "Target": "เป้าหมาย",
    "Target Quantity": "ปริมาณเป้าหมาย",
    "Target Weight": "น้ำหนักเป้าหมาย",
    "Total": "ทั้งหมด",
    "Total / Standard": "ทั้งหมด / มาตรฐาน",
    "Total Received Weight": "น้ำหนักรับทั้งหมด",
    "Type": "ประเภท",
    "Unchanged": "ไม่เปลี่ยนแปลง",
    "Unit": "หน่วย",
    "Update": "อัปเดต",
    "Upload": "อัปโหลด",
    "User": "ผู้ใช้งาน",
    "Username": "ชื่อผู้ใช้งาน",
    "Validate PO + Formula Sheet": "ตรวจสอบ PO + เอกสารสูตรการผลิต",
    "Validate workbook": "ตรวจสอบไฟล์",
    "Vendor Lot": "ล็อตผู้จำหน่าย",
    "Warehouse": "คลังสินค้า",
    "Weighed at": "ชั่งเมื่อ",
    "Weighing": "การชั่ง",
    "Weighing progress": "ความคืบหน้าการชั่ง",
    "Weighing Session Complete": "เซสชันการชั่งเสร็จสมบูรณ์",
    "Weight": "น้ำหนัก",
    "Weight reconciliation": "การกระทบยอดน้ำหนัก",
    "Weight reconciliation:": "การกระทบยอดน้ำหนัก:",
    "Center +": "กึ่งกลาง +",
    "MATERIAL TAG": "ป้ายวัตถุดิบ",
    "Large issuance: this batch creates {count} Tags.": (
        "การออกป้ายจำนวนมาก: ชุดนี้สร้างป้าย {count} รายการ"
    ),
    (
        "Use 3 × 2.5 inch paper, 100% scale, no margins, browser headers/footers "
        "off, and no Fit to Page. “Rendered” means the print page was prepared; "
        "it does not confirm physical printing."
    ): (
        "ใช้กระดาษขนาด 3 × 2.5 นิ้ว มาตราส่วน 100% ไม่มีระยะขอบ "
        "ปิดหัว/ท้ายกระดาษของเบราว์เซอร์ และปิด Fit to Page “แสดงหน้าพิมพ์แล้ว” "
        "หมายถึงจัดเตรียมหน้าพิมพ์แล้ว ไม่ได้ยืนยันว่าพิมพ์จริง"
    ),
    (
        "30 raw-material lines and their target weights are generated automatically for UAT."
    ): "ระบบสร้างวัตถุดิบ 30 บรรทัดและน้ำหนักเป้าหมายโดยอัตโนมัติสำหรับ UAT",
    (
        "All required weighings are recorded. This session will become read-only "
        "and cannot be cancelled or reopened."
    ): ("บันทึกการชั่งที่จำเป็นทั้งหมดแล้ว เซสชันนี้จะเป็นแบบอ่านอย่างเดียวและไม่สามารถยกเลิกหรือเปิดใหม่ได้"),
    (
        "Apply is blocked because this workbook has rejected rows. Correct it "
        "and upload another workbook."
    ): ("ไม่สามารถนำไปใช้ได้เนื่องจากไฟล์นี้มีแถวที่ถูกปฏิเสธ โปรดแก้ไขและอัปโหลดไฟล์ใหม่"),
    "Apply is blocked until all rejected rows are corrected in a new workbook.": (
        "ไม่สามารถนำไปใช้ได้จนกว่าจะแก้ไขแถวที่ถูกปฏิเสธทั้งหมดในไฟล์ใหม่"
    ),
    (
        "Calibration creates no Material Tag or print-event record. Use "
        "non-production test media only."
    ): ("การสอบเทียบไม่สร้างป้ายวัตถุดิบหรือประวัติการพิมพ์ ใช้เฉพาะสื่อทดสอบที่ไม่ใช่การผลิต"),
    (
        "Choose a material, scan its physical tag, then weigh its prepared Production Orders."
    ): "เลือกวัตถุดิบ สแกนป้ายจริง แล้วชั่งตามใบสั่งผลิตที่เตรียมไว้",
    "Choose any incomplete or partially completed Material from the queue.": (
        "เลือกวัตถุดิบที่ยังไม่เสร็จหรือเสร็จบางส่วนจากคิว"
    ),
    (
        "Completion closes this session and marks its Production Orders completed. "
        "Existing weighing records, Preweight IDs, weights, and traceability "
        "remain unchanged."
    ): (
        "การเสร็จสิ้นจะปิดเซสชันนี้และกำหนดใบสั่งผลิตเป็นเสร็จสมบูรณ์ "
        "โดยไม่เปลี่ยนบันทึกการชั่ง รหัสชั่งล่วงหน้า น้ำหนัก "
        "และข้อมูลสอบย้อนกลับเดิม"
    ),
    (
        "Containers in this batch share the same QR payload. Issued records become immutable."
    ): "ภาชนะในชุดนี้ใช้ข้อมูล QR เดียวกัน และรายการที่ออกแล้วไม่สามารถแก้ไขได้",
    "Create and review receiving-label batches from an approved Material.": (
        "สร้างและตรวจสอบชุดป้ายรับเข้าจากวัตถุดิบที่อนุมัติแล้ว"
    ),
    (
        "Development/UAT only. The system selects 30 active approved imported Materials and "
        "distributes the production quantity across their target weights automatically."
    ): (
        "สำหรับ Development/UAT เท่านั้น ระบบเลือกวัตถุดิบที่ใช้งานและผ่านการนำเข้า"
        "ที่อนุมัติแล้ว 30 รายการ และกระจายปริมาณการผลิตเป็นน้ำหนักเป้าหมายโดยอัตโนมัติ"
    ),
    "Mock Production Document History": "ประวัติเอกสารการผลิตจำลอง",
    "View and reprint previously generated Mock Production documents.": (
        "ดูและพิมพ์ซ้ำเอกสารการผลิตจำลองที่สร้างไว้ก่อนหน้า"
    ),
    "Back to Mock ERP": "กลับไปยัง Mock ERP",
    "Mock document history filters": "ตัวกรองประวัติเอกสารการผลิตจำลอง",
    "Production Date From": "วันที่ผลิตตั้งแต่",
    "Production Date To": "วันที่ผลิตถึง",
    "Clear filters": "ล้างตัวกรอง",
    "Created Date/Time": "วันที่/เวลาที่สร้าง",
    "View Production Order": "ดูใบสั่งผลิต",
    "Reprint Production Order": "พิมพ์ใบสั่งผลิตซ้ำ",
    "View Formula Sheet": "ดูเอกสารสูตรการผลิต",
    "Reprint Formula Sheet": "พิมพ์เอกสารสูตรการผลิตซ้ำ",
    "No Mock Production documents found.": "ไม่พบเอกสารการผลิตจำลอง",
    "Mock document history pages": "หน้าประวัติเอกสารการผลิตจำลอง",
    "Select a valid history date.": "เลือกวันที่ประวัติที่ถูกต้อง",
    "History start date cannot be after end date.": (
        "วันที่เริ่มต้นของประวัติต้องไม่อยู่หลังวันที่สิ้นสุด"
    ),
    "At least 30 active approved imported Materials are required.": (
        "ต้องมีวัตถุดิบที่ใช้งานและผ่านการนำเข้าที่อนุมัติแล้วอย่างน้อย 30 รายการ"
    ),
    "Issued data is immutable. Receiving details and print history are read-only.": (
        "ข้อมูลที่ออกแล้วไม่สามารถแก้ไขได้ รายละเอียดการรับและประวัติการพิมพ์เป็นแบบอ่านอย่างเดียว"
    ),
    "No Production Orders have been prepared for this weighing session yet.": (
        "ยังไม่ได้เตรียมใบสั่งผลิตสำหรับเซสชันการชั่งนี้"
    ),
    "Optional weighing flow organized by Formula and Production Order.": (
        "ขั้นตอนการชั่งทางเลือกที่จัดตามสูตรการผลิตและใบสั่งผลิต"
    ),
    ("Paper: 3 × 2.5 inches; scale 100%; margins none; headers/footers off; Fit to Page off."): (
        "กระดาษ: 3 × 2.5 นิ้ว; มาตราส่วน 100%; ไม่มีระยะขอบ; ปิดหัว/ท้ายกระดาษ; ปิดปรับให้พอดีหน้า"
    ),
    "Prepare Production Orders before weighing materials.": "เตรียมใบสั่งผลิตก่อนชั่งวัตถุดิบ",
    "Primary operator workspace organized by raw material.": "พื้นที่ทำงานหลักของผู้ปฏิบัติงานที่จัดตามวัตถุดิบ",
    "Review controlled administrative data and Material Master import.": (
        "ตรวจสอบข้อมูลดูแลระบบที่ควบคุมและการนำเข้าข้อมูลหลักวัตถุดิบ"
    ),
    (
        "Scan and validate each pair continuously. Every successful pair remains "
        "listed in this weighing session."
    ): ("สแกนและตรวจสอบแต่ละคู่ต่อเนื่อง คู่ที่สำเร็จทุกคู่จะคงอยู่ในรายการของเซสชันการชั่งนี้"),
    "Scan Production Orders and build the active weighing session.": (
        "สแกนใบสั่งผลิตและสร้างเซสชันการชั่งที่ใช้งานอยู่"
    ),
    (
        "Scan the 11-field Material Tag and enter the actual weight. Vendor Lot, "
        "QC status, expiry and remaining bag quantity do not block weighing."
    ): (
        "สแกนป้ายวัตถุดิบ 11 ช่องและกรอกน้ำหนักจริง ล็อตผู้จำหน่าย สถานะ QC "
        "วันหมดอายุ และปริมาณคงเหลือไม่ขัดขวางการชั่ง"
    ),
    (
        "Scan the physical Material Tag for the selected Material before entering a weight."
    ): "สแกนป้ายจริงของวัตถุดิบที่เลือกก่อนกรอกน้ำหนัก",
    "Select an active Material before creating a preview.": "เลือกวัตถุดิบที่เปิดใช้งานก่อนสร้างตัวอย่าง",
    (
        "Select an Active Finish Good from the approved Master. Code and Name cannot be overridden."
    ): ("เลือกสินค้าสำเร็จรูปที่เปิดใช้งานจากข้อมูลหลักที่อนุมัติ รหัสและชื่อไม่สามารถแก้ไขทับได้"),
    "Select a Material to begin weighing.": "เลือกวัตถุดิบเพื่อเริ่มการชั่ง",
    "Test utility for generating non-production PO and Formula documents.": (
        "เครื่องมือทดสอบสำหรับสร้างเอกสาร PO และสูตรการผลิตที่ไม่ใช่การผลิตจริง"
    ),
    "The validated Finish Goods Master rows were applied.": (
        "นำแถวข้อมูลหลักสินค้าสำเร็จรูปที่ตรวจสอบแล้วไปใช้เรียบร้อย"
    ),
    "The validated Material Master rows have been applied.": (
        "นำแถวข้อมูลหลักวัตถุดิบที่ตรวจสอบแล้วไปใช้เรียบร้อย"
    ),
    "These Production Orders will be processed together during material weighing.": (
        "ใบสั่งผลิตเหล่านี้จะถูกดำเนินการร่วมกันระหว่างการชั่งวัตถุดิบ"
    ),
    "This session is finalized and read-only.": "เซสชันนี้เสร็จสิ้นและเป็นแบบอ่านอย่างเดียว",
    "Upload and validate an approved .xlsx Material Master workbook.": (
        "อัปโหลดและตรวจสอบไฟล์ข้อมูลหลักวัตถุดิบ .xlsx ที่อนุมัติแล้ว"
    ),
    (
        "Upload and validate an approved .xlsx workbook. Validation creates a Preview only."
    ): "อัปโหลดและตรวจสอบไฟล์ .xlsx ที่อนุมัติ การตรวจสอบจะสร้างเพียงตัวอย่าง",
    "Verify the approved 3 × 2.5 inch label setup before printing.": (
        "ตรวจสอบการตั้งค่าป้าย 3 × 2.5 นิ้วที่อนุมัติก่อนพิมพ์"
    ),
    "Access denied.": "ปฏิเสธการเข้าถึง",
    "Administration and UAT Tools": "การดูแลระบบและเครื่องมือ UAT",
    "Code or Name": "รหัสหรือชื่อ",
    "Complete this weighing session to finalize session": "เสร็จสิ้นเซสชันการชั่งนี้เพื่อปิดเซสชัน",
    "Detected Material": "วัตถุดิบที่ตรวจพบ",
    "Enter reason (10–500 characters)": "กรอกเหตุผล (10–500 อักขระ)",
    "Finish Goods import pages": "หน้าผลการนำเข้าสินค้าสำเร็จรูป",
    "Finish Goods import row results": "ผลลัพธ์รายแถวของการนำเข้าสินค้าสำเร็จรูป",
    "Finish Goods search pages": "หน้าค้นหาสินค้าสำเร็จรูป",
    "Finalize session": "ปิดเซสชัน",
    "Font samples": "ตัวอย่างแบบอักษร",
    "Formula Sheet QR": "QR เอกสารสูตรการผลิต",
    "History pages": "หน้าประวัติ",
    "Invalid Material Tag": "ป้ายวัตถุดิบไม่ถูกต้อง",
    "Material import result pages": "หน้าผลการนำเข้าวัตถุดิบ",
    "Material import row results": "ผลลัพธ์รายแถวของการนำเข้าวัตถุดิบ",
    "Material pages": "หน้าวัตถุดิบ",
    "Material validation unavailable": "ไม่สามารถตรวจสอบวัตถุดิบได้",
    "Material-centric workflow progress": "ความคืบหน้าขั้นตอนตามวัตถุดิบ",
    "No print page has been rendered.": "ยังไม่มีการแสดงหน้าพิมพ์",
    "Partial Code or Name": "บางส่วนของรหัสหรือชื่อ",
    "Preview only": "ดูตัวอย่างเท่านั้น",
    "Print page rendered": "แสดงหน้าพิมพ์แล้ว",
    "Print view actions": "การดำเนินการหน้าพิมพ์",
    "Production Order QR": "QR ใบสั่งผลิต",
    "Production Orders for This Weighing Session": "ใบสั่งผลิตสำหรับเซสชันการชั่งนี้",
    "Progress": "ความคืบหน้า",
    "QR payload": "ข้อมูล QR",
    "Required and stored in print history.": "จำเป็นและจัดเก็บในประวัติการพิมพ์",
    "Required. The reason is stored in print history.": "จำเป็น เหตุผลจะถูกจัดเก็บในประวัติการพิมพ์",
    "Requested at": "ร้องขอเมื่อ",
    "Requested by": "ร้องขอโดย",
    "SAFE AREA": "พื้นที่ปลอดภัย",
    "Scan Material Tag to validate": "สแกนป้ายวัตถุดิบเพื่อตรวจสอบ",
    "Scan Production Order + Formula Sheet": "สแกนใบสั่งผลิต + เอกสารสูตรการผลิต",
    "Scope": "ขอบเขต",
    "Selected Material": "วัตถุดิบที่เลือก",
    "Top/left offset": "ระยะเยื้องด้านบน/ซ้าย",
    "Padding / QR": "ระยะขอบภายใน / QR",
    "Font scale / line spacing": "ขนาดอักษร / ระยะห่างบรรทัด",
    "Validating…": "กำลังตรวจสอบ…",
    "Vendor Lot:": "ล็อตผู้จำหน่าย:",
    "Weight:": "น้ำหนัก:",
    "Received:": "วันที่รับ:",
    "Expiry:": "วันหมดอายุ:",
    "Code:": "รหัส:",
    "ERP Preweight QR": "QR การชั่งล่วงหน้า ERP",
    "Material Tag QR Code": "QR ป้ายวัตถุดิบ",
    "Reprint Tag": "พิมพ์ป้ายซ้ำ",
    "Select a valid active Material.": "เลือกวัตถุดิบที่เปิดใช้งานและถูกต้อง",
    "Select a Finish Good": "เลือกสินค้าสำเร็จรูป",
    "Select an Active Finish Good from the approved Master.": (
        "เลือกสินค้าสำเร็จรูปที่เปิดใช้งานจากข้อมูลหลักที่อนุมัติ"
    ),
    "Prepare Production Orders": "เตรียมใบสั่งผลิต",
    "Prepare Work Set": "เตรียมชุดงาน",
    "Search issued batches and inspect auditable print history.": (
        "ค้นหาชุดที่ออกแล้วและตรวจสอบประวัติการพิมพ์ที่สอบทานได้"
    ),
    "Weigh Materials": "ชั่งวัตถุดิบ",
    "Weighing {po}": "การชั่ง {po}",
    "at station": "ที่สถานีงาน",
    (
        "required weighings are recorded. This session will become read-only and "
        "cannot be cancelled or reopened."
    ): ("การชั่งที่จำเป็นได้รับการบันทึกแล้ว เซสชันนี้จะเป็นแบบอ่านอย่างเดียวและไม่สามารถยกเลิกหรือเปิดใหม่ได้"),
    "FORMULA SHEET": "เอกสารสูตรการผลิต",
    "MOCK ERP — DEVELOPMENT / UAT": "ERP จำลอง — DEVELOPMENT / UAT",
    "PRODUCTION ORDER": "ใบสั่งผลิต",
    (
        "QR payload identifies this Production Order in the UAT system. Print "
        "this page and scan the QR at the Preweight station."
    ): ("ข้อมูล QR ระบุใบสั่งผลิตนี้ในระบบ UAT พิมพ์หน้านี้และสแกน QR ที่สถานีชั่งล่วงหน้า"),
    "Raw Materials": "วัตถุดิบ",
    "Total target weight": "น้ำหนักเป้าหมายรวม",
    "auto-generated lines": "บรรทัดที่สร้างอัตโนมัติ",
    "MATCH": "ตรงกัน",
    "PO + FORMULA MATCHED": "PO + สูตรการผลิตตรงกัน",
    "Production Orders completed": "ใบสั่งผลิตเสร็จสมบูรณ์",
    (
        "Production Order statuses and existing weighing records will not be "
        "changed. The current material selection will be cleared."
    ): ("สถานะใบสั่งผลิตและบันทึกการชั่งเดิมจะไม่เปลี่ยนแปลง ระบบจะล้างวัตถุดิบที่เลือกอยู่"),
    (
        "Removes the current group of Production Orders from this weighing "
        "session. No weighing records will be created."
    ): ("นำกลุ่มใบสั่งผลิตปัจจุบันออกจากเซสชันการชั่งนี้ โดยจะไม่สร้างบันทึกการชั่ง"),
    "Changing Material will discard unsaved weight input. Continue?": (
        "การเปลี่ยนวัตถุดิบจะละทิ้งน้ำหนักที่ยังไม่ได้บันทึก ดำเนินการต่อหรือไม่"
    ),
    "Scanned Material": "วัตถุดิบที่สแกน",
    "Scanned Material does not match the selected Material.": (
        "ข้อความแจ้งเตือน / Message: วัตถุดิบที่สแกนไม่ตรงกับวัตถุดิบที่เลือก"
    ),
    "UN-MATCH": "ไม่ตรงกัน",
    "UN-MATCH — Material validation unavailable": "ไม่ตรงกัน — ไม่สามารถตรวจสอบวัตถุดิบได้",
    "Uploaded": "อัปโหลดเมื่อ",
    "by": "โดย",
    "no Finish Good has changed.": "ยังไม่มีการเปลี่ยนแปลงสินค้าสำเร็จรูป",
    "no Material record has changed yet.": "ยังไม่มีการเปลี่ยนแปลงรายการวัตถุดิบ",
    "This field is required.": "จำเป็นต้องกรอกข้อมูลนี้",
    "Invalid input.": "ข้อมูลไม่ถูกต้อง",
    "Invalid username or password.": "ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง",
    "Selected station is unavailable.": "สถานีงานที่เลือกไม่พร้อมใช้งาน",
    "You have been logged out.": "ออกจากระบบแล้ว",
    "Scan and validate a Material Tag before weighing.": "สแกนและตรวจสอบป้ายวัตถุดิบก่อนชั่ง",
    "All required weighings are complete. Complete this weighing session.": (
        "การชั่งที่จำเป็นทั้งหมดเสร็จสมบูรณ์ โปรดเสร็จสิ้นเซสชันการชั่งนี้"
    ),
    "Material session ended. Scan the next Material Tag.": "สิ้นสุดเซสชันวัตถุดิบแล้ว โปรดสแกนป้ายวัตถุดิบถัดไป",
    "Material Tags issued successfully.": "ออกป้ายวัตถุดิบสำเร็จ",
    "Material Master import applied successfully.": "นำเข้าข้อมูลหลักวัตถุดิบสำเร็จ",
    "Finish Goods Master import applied successfully.": "นำเข้าข้อมูลหลักสินค้าสำเร็จรูปสำเร็จ",
    "Finished Good Item Code and Name are required.": "จำเป็นต้องระบุรหัสและชื่อสินค้าสำเร็จรูป",
    "Mock Production Order and Formula Sheet created.": "สร้างใบสั่งผลิตและเอกสารสูตรการผลิตจำลองแล้ว",
    "Date is required. Use dd/mm/yyyy.": "จำเป็นต้องระบุวันที่ ใช้รูปแบบ dd/mm/yyyy",
    "Enter a valid date in dd/mm/yyyy format.": "กรอกวันที่ที่ถูกต้องในรูปแบบ dd/mm/yyyy",
    "Production Lot must be a text value.": "ล็อตการผลิตต้องเป็นข้อความ",
    "Production Lot is required.": "จำเป็นต้องระบุล็อตการผลิต",
    "Production Lot must not contain control characters.": "ล็อตการผลิตต้องไม่มีอักขระควบคุม",
    "Production Order No. already exists.": "เลขที่ใบสั่งผลิตมีอยู่แล้ว",
    "Formula Sheet No. already exists.": "เลขที่เอกสารสูตรการผลิตมีอยู่แล้ว",
    "Finished Good Item Code already exists with another name.": "รหัสสินค้าสำเร็จรูปมีอยู่แล้วโดยใช้ชื่ออื่น",
    "Workbook values must not contain control characters.": "ค่าในไฟล์ต้องไม่มีอักขระควบคุม",
    "The uploaded workbook is empty.": "ไฟล์ที่อัปโหลดว่างเปล่า",
    "The workbook exceeds the permitted upload size.": "ไฟล์มีขนาดเกินที่อนุญาตให้อัปโหลด",
    "The uploaded file could not be read as an .xlsx workbook.": (
        "ไม่สามารถอ่านไฟล์ที่อัปโหลดเป็นไฟล์ .xlsx ได้"
    ),
    "The workbook must contain only the Sheet1 worksheet.": "ไฟล์ต้องมีเฉพาะแผ่นงาน Sheet1",
    "The Sheet1 worksheet is empty.": "แผ่นงาน Sheet1 ว่างเปล่า",
    "Header cells must not contain formulas.": "เซลล์หัวตารางต้องไม่มีสูตร",
    "Sheet1 headers must be exactly: FINISH GOODS_CODE, CATEGORY_NO, NAME.": (
        "หัวตาราง Sheet1 ต้องเป็น FINISH GOODS_CODE, CATEGORY_NO, NAME เท่านั้น"
    ),
    "The workbook contains no Finish Goods rows.": "ไฟล์ไม่มีแถวสินค้าสำเร็จรูป",
    "The workbook contains more rows than permitted.": "ไฟล์มีจำนวนแถวเกินที่อนุญาต",
    "Values outside the approved three columns are not accepted.": "ไม่ยอมรับค่านอกสามคอลัมน์ที่อนุมัติ",
    "Required cells must contain values, not formulas.": "เซลล์ที่จำเป็นต้องมีค่า ไม่ใช่สูตร",
    "FINISH GOODS_CODE, CATEGORY_NO, and NAME are required.": (
        "จำเป็นต้องระบุ FINISH GOODS_CODE, CATEGORY_NO และ NAME"
    ),
    "One or more values exceed the permitted field length.": "มีค่าอย่างน้อยหนึ่งค่าที่ยาวเกินที่อนุญาต",
    "CATEGORY_NO must be F/G.": "CATEGORY_NO ต้องเป็น F/G",
    "Finish Goods import preview was not found.": "ไม่พบตัวอย่างการนำเข้าสินค้าสำเร็จรูป",
    "Only the preview uploader can apply this import.": "เฉพาะผู้อัปโหลดตัวอย่างเท่านั้นที่นำเข้ารายการนี้ได้",
    "Only a valid preview can be applied.": "นำไปใช้ได้เฉพาะตัวอย่างที่ถูกต้อง",
    "The persisted preview failed integrity validation or contains rejected rows.": (
        "ตัวอย่างที่จัดเก็บไม่ผ่านการตรวจสอบความถูกต้องหรือมีแถวที่ถูกปฏิเสธ"
    ),
    "The persisted preview contains an invalid Finish Goods row.": (
        "ตัวอย่างที่จัดเก็บมีแถวสินค้าสำเร็จรูปที่ไม่ถูกต้อง"
    ),
    "The persisted preview contains duplicate Finish Goods codes.": "ตัวอย่างที่จัดเก็บมีรหัสสินค้าสำเร็จรูปซ้ำ",
    "Maximum Tags must be an integer between 1 and 200.": (
        "จำนวนป้ายสูงสุดต้องเป็นจำนวนเต็มระหว่าง 1 ถึง 200"
    ),
    "Calculated container weights do not reconcile to Total Received Weight.": (
        "น้ำหนักภาชนะที่คำนวณไม่ตรงกับน้ำหนักรับทั้งหมด"
    ),
    "Receiving Date must be a valid date.": "วันที่รับต้องเป็นวันที่ที่ถูกต้อง",
    "Generated Material Tag QR payload is not deterministic.": "ข้อมูล QR ป้ายวัตถุดิบที่สร้างไม่คงที่แน่นอน",
    "Receiving Date must use dd/mm/yyyy.": "วันที่รับต้องใช้รูปแบบ dd/mm/yyyy",
    "Receiving Date must be between 01/01/2000 and 31/12/2100.": (
        "วันที่รับต้องอยู่ระหว่าง 01/01/2000 ถึง 31/12/2100"
    ),
    "Draft lifetime configuration is invalid.": "การกำหนดอายุแบบร่างไม่ถูกต้อง",
    "Draft integrity validation failed.": "การตรวจสอบความถูกต้องของแบบร่างล้มเหลว",
    "Material Tag draft was not found.": "ไม่พบแบบร่างป้ายวัตถุดิบ",
    "Only the draft creator may confirm issuance.": "เฉพาะผู้สร้างแบบร่างเท่านั้นที่ยืนยันการออกป้ายได้",
    "Only a previewed draft may be issued.": "ออกป้ายได้เฉพาะแบบร่างที่ดูตัวอย่างแล้ว",
    "This Material Tag draft has expired.": "แบบร่างป้ายวัตถุดิบนี้หมดอายุแล้ว",
    "Generated QR payload failed validation.": "ข้อมูล QR ที่สร้างไม่ผ่านการตรวจสอบ",
    "A unique Material Tag batch number could not be generated.": (
        "ไม่สามารถสร้างหมายเลขชุดป้ายวัตถุดิบที่ไม่ซ้ำได้"
    ),
    "Material Tag issuance failed safely; no records were issued.": (
        "การออกป้ายวัตถุดิบล้มเหลวอย่างปลอดภัย โดยไม่มีการออกข้อมูล"
    ),
    "Stored Material Tag QR payload is invalid.": "ข้อมูล QR ป้ายวัตถุดิบที่จัดเก็บไม่ถูกต้อง",
    "Reprint reason must contain 10 to 500 characters.": "เหตุผลในการพิมพ์ซ้ำต้องมี 10 ถึง 500 อักขระ",
    "Issued Material Tag batch was not found.": "ไม่พบชุดป้ายวัตถุดิบที่ออกแล้ว",
    "Material Name is too long for a readable 3 x 2.5 inch label.": (
        "ชื่อวัตถุดิบยาวเกินกว่าจะแสดงบนป้ายขนาด 3 x 2.5 นิ้วให้อ่านได้"
    ),
    "Selected Material Tag does not belong to this batch.": "ป้ายวัตถุดิบที่เลือกไม่ได้อยู่ในชุดนี้",
    "Original printing must render the complete batch.": "การพิมพ์ต้นฉบับต้องแสดงทั้งชุด",
    "Unknown print intent.": "ไม่รู้จักวัตถุประสงค์การพิมพ์",
    "Stored QR payload could not be rendered.": "ไม่สามารถแสดงข้อมูล QR ที่จัดเก็บได้",
    "Print page rendering failed safely.": "การแสดงหน้าพิมพ์ล้มเหลวอย่างปลอดภัย",
    "Material is unavailable.": "วัตถุดิบไม่พร้อมใช้งาน",
    "Material is not required by this weighing session.": "เซสชันการชั่งนี้ไม่ต้องใช้วัตถุดิบนี้",
    "UN-MATCH — Material is not required by this weighing session.": (
        "ไม่ตรงกัน — เซสชันการชั่งนี้ไม่ต้องใช้วัตถุดิบนี้"
    ),
    "Queue item is unavailable.": "รายการคิวไม่พร้อมใช้งาน",
    "This Production Order material is already completed.": "วัตถุดิบของใบสั่งผลิตนี้เสร็จสมบูรณ์แล้ว",
    "Material Tag QR must contain exactly 11 fields.": "QR ป้ายวัตถุดิบต้องมี 11 ช่องพอดี",
    "Material Tag receiving date must use DD/MM/YYYY.": "วันที่รับในป้ายวัตถุดิบต้องใช้รูปแบบ DD/MM/YYYY",
    "Actual Weight must be numeric and greater than zero.": "น้ำหนักจริงต้องเป็นตัวเลขและมากกว่าศูนย์",
    "Daily Preweight ID sequence is exhausted.": "ลำดับรหัสชั่งล่วงหน้าประจำวันหมดแล้ว",
    "Production Order is not ready for weighing.": "ใบสั่งผลิตยังไม่พร้อมสำหรับการชั่ง",
    "Formula line is unavailable.": "บรรทัดสูตรการผลิตไม่พร้อมใช้งาน",
    "This Formula line has already been weighed successfully.": "บรรทัดสูตรการผลิตนี้ชั่งสำเร็จแล้ว",
    (
        "The Formula line or Preweight ID was saved by another request. "
        "Refresh and retry."
    ): (
        "บรรทัดสูตรการผลิตหรือรหัสชั่งล่วงหน้าถูกบันทึกโดยคำขออื่น "
        "โปรดรีเฟรชและลองใหม่"
    ),
    "The uploaded file is not a valid .xlsx workbook.": "ไฟล์ที่อัปโหลดไม่ใช่ไฟล์ .xlsx ที่ถูกต้อง",
    "The workbook contains too many internal files.": "ไฟล์มีไฟล์ภายในมากเกินไป",
    "The workbook contains an unsafe internal path.": "ไฟล์มีเส้นทางภายในที่ไม่ปลอดภัย",
    "The workbook expands beyond the permitted size.": "ไฟล์ขยายเกินขนาดที่อนุญาต",
    "Macro-enabled workbooks are not accepted.": "ไม่ยอมรับไฟล์ที่เปิดใช้แมโคร",
    "The workbook contains malformed or unsafe XML.": "ไฟล์มี XML ที่ผิดรูปแบบหรือไม่ปลอดภัย",
    "Workbooks containing external links are not accepted.": "ไม่ยอมรับไฟล์ที่มีลิงก์ภายนอก",
    "Merged cells are not accepted in Sheet1.": "ไม่ยอมรับเซลล์ผสานใน Sheet1",
    "Sheet1 headers must be exactly: ITEM CODE, CATEGORY_NO, NAME.": (
        "หัวตาราง Sheet1 ต้องเป็น ITEM CODE, CATEGORY_NO, NAME เท่านั้น"
    ),
    "The workbook contains no Material rows.": "ไฟล์ไม่มีแถววัตถุดิบ",
    "ITEM CODE, CATEGORY_NO, and NAME are required.": "จำเป็นต้องระบุ ITEM CODE, CATEGORY_NO และ NAME",
    "CATEGORY_NO must be MAT.": "CATEGORY_NO ต้องเป็น MAT",
    "ITEM CODE occurs more than once in this workbook.": "ITEM CODE ปรากฏมากกว่าหนึ่งครั้งในไฟล์นี้",
    "The persisted preview counts failed integrity validation.": (
        "จำนวนในตัวอย่างที่จัดเก็บไม่ผ่านการตรวจสอบความถูกต้อง"
    ),
    "This workbook contains rejected rows. Correct it and upload a new workbook.": (
        "ไฟล์นี้มีแถวที่ถูกปฏิเสธ โปรดแก้ไขและอัปโหลดไฟล์ใหม่"
    ),
    "The persisted Excel row identities are invalid.": "รหัสแถว Excel ที่จัดเก็บไม่ถูกต้อง",
    "The persisted row classification is invalid.": "ประเภทแถวที่จัดเก็บไม่ถูกต้อง",
    "The persisted preview contains an invalid value.": "ตัวอย่างที่จัดเก็บมีค่าที่ไม่ถูกต้อง",
    "The persisted preview contains an invalid Material row.": "ตัวอย่างที่จัดเก็บมีแถววัตถุดิบที่ไม่ถูกต้อง",
    "The persisted preview contains duplicate Material codes.": "ตัวอย่างที่จัดเก็บมีรหัสวัตถุดิบซ้ำ",
    "Material import preview was not found.": "ไม่พบตัวอย่างการนำเข้าวัตถุดิบ",
    "Production Order is already included in this weighing session.": "ใบสั่งผลิตอยู่ในเซสชันการชั่งนี้แล้ว",
    "Production Order is already included in another station's weighing session.": (
        "ใบสั่งผลิตอยู่ในเซสชันการชั่งของสถานีอื่นแล้ว"
    ),
    (
        "Production Order and Formula matched and were added to this weighing "
        "session."
    ): "ใบสั่งผลิตและสูตรการผลิตตรงกันและเพิ่มในเซสชันการชั่งนี้แล้ว",
    "No active weighing session is available.": "ไม่มีเซสชันการชั่งที่เปิดใช้งาน",
    (
        "This weighing session cannot be cancelled because weighing records "
        "already exist."
    ): "ไม่สามารถยกเลิกเซสชันการชั่งนี้ได้เนื่องจากมีบันทึกการชั่งแล้ว",
    "Weighing session is unavailable.": "เซสชันการชั่งไม่พร้อมใช้งาน",
    "This weighing session is already completed.": "เซสชันการชั่งนี้เสร็จสมบูรณ์แล้ว",
    "Weighing session completion state is inconsistent.": "สถานะการเสร็จสิ้นของเซสชันการชั่งไม่สอดคล้องกัน",
    "Only an active, ready weighing session can be completed.": (
        "เสร็จสิ้นได้เฉพาะเซสชันการชั่งที่เปิดใช้งานและพร้อม"
    ),
    "Complete every required weighing before completing this weighing session.": (
        "ชั่งรายการที่จำเป็นทั้งหมดก่อนเสร็จสิ้นเซสชันการชั่งนี้"
    ),
    "Weighing session completed.": "เซสชันการชั่งเสร็จสมบูรณ์แล้ว",
    "Production Order not found.": "ไม่พบใบสั่งผลิต",
    "Cancelled Production Order cannot start.": "ไม่สามารถเริ่มใบสั่งผลิตที่ยกเลิกแล้ว",
    "Completed Production Order cannot start.": "ไม่สามารถเริ่มใบสั่งผลิตที่เสร็จสมบูรณ์แล้ว",
    "Formula Sheet not found.": "ไม่พบเอกสารสูตรการผลิต",
    "Formula Sheet is unavailable.": "เอกสารสูตรการผลิตไม่พร้อมใช้งาน",
    "ERROR: Production Order and Formula Sheet do not match.": (
        "ข้อผิดพลาด: ใบสั่งผลิตและเอกสารสูตรการผลิตไม่ตรงกัน"
    ),
    "ERROR: Production Lot does not match the Formula Sheet.": (
        "ข้อผิดพลาด: ล็อตการผลิตไม่ตรงกับเอกสารสูตรการผลิต"
    ),
    "Production Order and Formula Sheet matched; ready for weighing.": (
        "ใบสั่งผลิตและเอกสารสูตรการผลิตตรงกัน พร้อมสำหรับการชั่ง"
    ),
}


def translate(text: str, /, **values) -> str:
    """Return Thai first and English second, with safely formatted variables."""
    thai = TRANSLATIONS.get(text)
    if thai is None:
        raise KeyError(f"Missing UI translation: {text}")
    return f"{thai} / {text}".format_map(values)


def status_label(value) -> str:
    """Present a stored status without changing the stored enum/code value."""
    raw = "" if value is None else str(value)
    display = raw.replace("_", " ").title() if raw.isupper() else raw
    return translate(display) if display in TRANSLATIONS else display


def message(text) -> str:
    """Translate service/form feedback while preserving its original English evidence."""
    raw = str(text)
    if raw in TRANSLATIONS:
        return translate(raw)
    if " / " in raw:
        return raw
    patterns = (
        (r"^MATCH — (.+)$", r"ตรงกัน — \1"),
        (r"^Selected (.+)\.$", r"เลือก \1 แล้ว"),
        (r"^Weighing completed as (.+)\.$", r"ชั่งเสร็จสมบูรณ์เป็น \1"),
    )
    for pattern, thai_pattern in patterns:
        if re.match(pattern, raw):
            return f"{re.sub(pattern, thai_pattern, raw)} / {raw}"
    dynamic_patterns = (
        (r"^Current station cannot weigh (.+)\.$", r"สถานีงานปัจจุบันไม่สามารถชั่ง \1 ได้"),
        (
            r"^UN-MATCH — Current station cannot weigh (.+)\.$",
            r"ไม่ตรงกัน — สถานีงานปัจจุบันไม่สามารถชั่ง \1 ได้",
        ),
        (
            r"^Wrong Material: expected (.+), scanned (.+)\.$",
            r"วัตถุดิบไม่ถูกต้อง: ต้องการ \1 แต่สแกน \2",
        ),
        (r"^(.+) queue is already completed\.$", r"คิว \1 เสร็จสมบูรณ์แล้ว"),
        (
            r"^Production Lot must not exceed (\d+) characters\.$",
            r"ล็อตการผลิตต้องยาวไม่เกิน \1 อักขระ",
        ),
        (
            r"^Cancelled this weighing session \((\d+) Production Order\(s\) "
            r"removed\)\. No weighing record was created\.$",
            r"ยกเลิกเซสชันการชั่งนี้แล้ว (นำใบสั่งผลิตออก \1 รายการ) "
            r"โดยไม่สร้างบันทึกการชั่ง",
        ),
        (
            r"^Product (.+) already has Production Lot (.+)\. Use a different "
            r"Production Lot for this Product\.$",
            r"ผลิตภัณฑ์ \1 มีล็อตการผลิต \2 แล้ว "
            r"โปรดใช้ล็อตการผลิตอื่นสำหรับผลิตภัณฑ์นี้",
        ),
        (
            r"^Calculated Tag count must be between 1 and (\d+)\.$",
            r"จำนวนป้ายที่คำนวณต้องอยู่ระหว่าง 1 ถึง \1",
        ),
    )
    for pattern, thai_pattern in dynamic_patterns:
        if re.match(pattern, raw):
            return f"{re.sub(pattern, thai_pattern, raw)} / {raw}"
    field_patterns = (
        (r"^(.+) is required\.$", r"จำเป็นต้องระบุ {field}"),
        (r"^(.+) must be finite and greater than zero\.$", r"{field} ต้องเป็นค่าจำกัดและมากกว่าศูนย์"),
        (r"^(.+) may contain no more than three decimals\.$", r"{field} มีทศนิยมได้ไม่เกินสามตำแหน่ง"),
        (r"^(.+) must be greater than zero\.$", r"{field} ต้องมากกว่าศูนย์"),
        (r"^(.+) must not contain '\|'\.$", r"{field} ต้องไม่มีอักขระ '|'"),
        (r"^(.+) must not contain control characters\.$", r"{field} ต้องไม่มีอักขระควบคุม"),
        (r"^(.+) must not exceed (\d+) characters\.$", r"{field} ต้องยาวไม่เกิน {limit} อักขระ"),
        (
            r"^(.+) must be a finite Decimal-compatible value with at most three decimals\.$",
            r"{field} ต้องเป็นค่าจำกัดที่ใช้เป็นเลขทศนิยมได้และมีทศนิยมไม่เกินสามตำแหน่ง",
        ),
    )
    for pattern, thai_template in field_patterns:
        match = re.match(pattern, raw)
        if match:
            field = match.group(1)
            translated_field = TRANSLATIONS.get(field, field)
            thai = thai_template.format(
                field=translated_field,
                limit=match.group(2) if match.lastindex and match.lastindex > 1 else "",
            )
            return f"{thai} / {raw}"
    return f"ข้อความแจ้งเตือน / Message: {raw}"
