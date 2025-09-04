# PHLPost

The `raw.json` data is extracted from https://phlpost.gov.ph/zip-code-locator by
running the following in the browser's console:

```js
var table = $("#offices").DataTable();
var allData = table.rows().data().toArray();

var cleanData = allData
  .filter(function (row) {
    return (
      row &&
      row.length === 4 &&
      row.some(function (cell) {
        return cell && cell.toString().trim() !== "";
      })
    );
  })
  .map(function (row) {
    var zipCode = row[3] ? row[3].toString().trim() : "";
    var cityMunicipality = row[2] ? row[2].toString().trim() : "";

    // Fix erroneous data: Cajidiocan's zip code should be 5512, not "Cajidiocan"
    if (cityMunicipality === "Cajidiocan" && zipCode === "Cajidiocan") {
      zipCode = "5512";
    }

    return {
      region: row[0] ? row[0].toString().trim() : "",
      province: row[1] ? row[1].toString().trim() : "",
      city_municipality: cityMunicipality,
      zip_code: zipCode,
    };
  })
  .sort(function (a, b) {
    return a.zip_code.localeCompare(b.zip_code, undefined, { numeric: true });
  });

console.log(cleanData);
console.log("Total entries:", cleanData.length);
```

You will notice that we are manually replacing `Cajidiocan` with `5512` as it's
currently incorrect in the PHLPost website itself.
