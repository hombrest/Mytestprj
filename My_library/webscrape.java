
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;

import java.io.IOException;

public class WebScraper {
    public static void main(String[] args) {
        try {
            // Connect to the webpage
            String url = "your_webpage_url_here";
            Document doc = Jsoup.connect(url)
                    .userAgent("Mozilla/5.0")
                    .get();

            // Find the form with name "dataform"
            Element form = doc.select("form[name=dataform]").first();
            
            if (form != null) {
                // Find the table within the form
                Element table = form.select("table").first();
                
                if (table != null) {
                    // Get all rows
                    Elements rows = table.select("tr");
                    
                    // Process each row
                    for (Element row : rows) {
                        Elements cells = row.select("td");
                        
                        if (cells.size() >= 2) {
                            // Get content of first and second column
                            String firstColumn = cells.get(0).html(); // Using html() to preserve formatting
                            String secondColumn = cells.get(1).html();
                            
                            // Convert HTML line breaks to actual line breaks
                            firstColumn = firstColumn.replaceAll("<br\\s*/*>", "\n")
                                                   .replaceAll("&nbsp;", " ")
                                                   .trim();
                            secondColumn = secondColumn.replaceAll("<br\\s*/*>", "\n")
                                                     .replaceAll("&nbsp;", " ")
                                                     .trim();
                            
                            // Remove any other HTML tags while keeping the content
                            firstColumn = Jsoup.parse(firstColumn).text();
                            secondColumn = Jsoup.parse(secondColumn).text();
                            
                            // Print the columns
                            System.out.println("Column 1:");
                            System.out.println(firstColumn);
                            System.out.println("Column 2:");
                            System.out.println(secondColumn);
                            System.out.println("-------------------");
                        }
                    }
                } else {
                    System.out.println("Table not found within the form");
                }
            } else {
                System.out.println("Form with name 'dataform' not found");
            }
            
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}


// *******

import java.io.PrintWriter;

// ... inside the main method after processing the cells ...

try (PrintWriter writer = new PrintWriter(new FileWriter("output.txt"))) {
    for (Element row : rows) {
        Elements cells = row.select("td");
        
        if (cells.size() >= 2) {
            String firstColumn = cells.get(0).html()
                    .replaceAll("<br\\s*/*>", "\n")
                    .replaceAll("&nbsp;", " ")
                    .trim();
            String secondColumn = cells.get(1).html()
                    .replaceAll("<br\\s*/*>", "\n")
                    .replaceAll("&nbsp;", " ")
                    .trim();
            
            firstColumn = Jsoup.parse(firstColumn).text();
            secondColumn = Jsoup.parse(secondColumn).text();
            
            writer.println("Column 1:");
            writer.println(firstColumn);
            writer.println("Column 2:");
            writer.println(secondColumn);
            writer.println("-------------------");
        }
    }
}
