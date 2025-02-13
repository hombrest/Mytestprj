import com.example.excelimport.service.ExcelService;
import com.example.excelimport.dto.ResponseDTO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Slf4j
public class ExcelController {
    private final ExcelService excelService;

    @PostMapping("/upload")
    public ResponseEntity<ResponseDTO> uploadFile(@RequestParam("file") MultipartFile file) {
        try {
            // Validate file
            if (file.isEmpty()) {
                return ResponseEntity
                    .status(HttpStatus.BAD_REQUEST)
                    .body(new ResponseDTO(false, "Please upload a file", null));
            }

            // Validate file extension
            String filename = file.getOriginalFilename();
            if (!filename.endsWith(".xlsx") && !filename.endsWith(".xls")) {
                return ResponseEntity
                    .status(HttpStatus.BAD_REQUEST)
                    .body(new ResponseDTO(false, "Please upload an Excel file", null));
            }

            // Process the file
            excelService.importExcelFile(file);

            return ResponseEntity.ok(
                new ResponseDTO(true, "File processed successfully", null)
            );

        } catch (Exception e) {
            log.error("Error processing file: ", e);
            return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ResponseDTO(false, "Failed to process file: " + e.getMessage(), null));
        }
    }

    @GetMapping("/employees")
    public ResponseEntity<ResponseDTO> getAllEmployees() {
        try {
            return ResponseEntity.ok(
                new ResponseDTO(true, "Employees retrieved successfully", 
                    excelService.getAllEmployees())
            );
        } catch (Exception e) {
            log.error("Error retrieving employees: ", e);
            return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ResponseDTO(false, "Failed to retrieve employees", null));
        }
    }
}
