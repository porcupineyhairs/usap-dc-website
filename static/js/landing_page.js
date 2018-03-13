$(document).ready(function() {
    $('#get-data').click(function() {
	
    });
    new MapClient();



	function MapClient() {
		proj4.defs('EPSG:3031', '+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs');
	    var projection = ol.proj.get('EPSG:3031');
	    projection.setWorldExtent([-180.0000, -90.0000, 180.0000, -60.0000]);
	    projection.setExtent([-8200000, -8200000, 8200000, 8200000]);
		var api_url = 'http://api.usap-dc.org:81/wfs?';

	    var map = new ol.Map({	// set to GMRT SP bounds
		target: 'map',
		interactions: ol.interaction.defaults({mouseWheelZoom:false}),
		view: new ol.View({
		    center: [0, 0],
		    zoom: 1,
		    projection: projection,
		    minZoom: 1,
		    maxZoom: 10
		})
	    });


	   var scar = new ol.layer.Tile({
		type: 'base',
		title: "SCAR Coastlines",
		source: new ol.source.TileWMS({
		    url: "http://nsidc.org/cgi-bin/mapserv?",
		    params: {
			map: '/WEB/INTERNET/MMS/atlas/epsg3031_grids.map',
			layers: 'land',
			srs: 'epsg:3031',
			bgcolor: '0x00ffff',
			format: 'image/jpeg'
		    }
		})
	    });
	    map.addLayer(scar);

	    var gmrt = new ol.layer.Tile({
		type: 'base',
		title: "GMRT Synthesis",
		source: new ol.source.TileWMS({
		    url: "http://gmrt.marine-geo.org/cgi-bin/mapserv?map=/public/mgg/web/gmrt.marine-geo.org/htdocs/services/map/wms_sp.map",
		    params: {
			layers: 'South_Polar_Bathymetry'
		    }
		})
	    });
	    map.addLayer(gmrt);


	    var gmrtmask = new ol.layer.Tile({
		type: 'base',
		visible: false,
		title: "GMRT Synthesis-Mask",
		source: new ol.source.TileWMS({
		    url: "http://gmrt.marine-geo.org/cgi-bin/mapserv?map=/public/mgg/web/gmrt.marine-geo.org/htdocs/services/map/wms_sp_mask.map",
		    params: {
			layers: 'South_Polar_Bathymetry'
		    }
		})
	    });
	    map.addLayer(gmrtmask);


	    var gma_modis = new ol.layer.Tile({
		// type: 'base',
		title: "GMA MODIS Mosaic",
		visible: false,
		source: new ol.source.TileWMS({
		    url: "http://nsidc.org/cgi-bin/atlas_south?",
		    params: {
			layers: 'antarctica_satellite_image',
			format:'image/png',
			srs: 'epsg:3031',
			transparent: true
		    }
		})
	    });
	    map.addLayer(gma_modis);

	    var modis = new ol.layer.Tile({
		title: "MODIS Mosaic",
		visible: false,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: 'MODIS',
			transparent: true
		    }
		})
	    });
	    map.addLayer(modis);

	    var lima = new ol.layer.Tile({
		// type: 'base',
		title: "LIMA 240m",
		visible: true,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: "LIMA 240m",
			transparent: true
		    }
		})
	    });
	    map.addLayer(lima);

	    var frank_modis = new ol.layer.Tile({
		// type: 'base',
		title: "Franks MODIS Mosaic",
		visible: false,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: "Franks MODIS",
			transparent: true
		    }
		})
	    });
	    map.addLayer(frank_modis);


	    var tracks = new ol.layer.Tile({
		title: "USAP R/V Cruises",
		visible: false,
		source: new ol.source.TileWMS({
		    url: "http://www.marine-geo.org/services/mapserver/wmscontrolpointsSP?",
		    params: {
			layers: 'Tracks-Lines',
			transparent: true
		    }
		})
	    });
	    map.addLayer(tracks);
	    
	    var difINT = new ol.layer.Tile({
		title: "Integrated System Science",
		visible: false,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: 'Integrated',
			transparent: true
		    }
		})
	    });
	    map.addLayer(difINT);
		
	    var difEarthSciences = new ol.layer.Tile({
		title: "Earth Sciences",
		visible: false,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: 'Earth',
			transparent: true
		    }
		})
	    });
	    map.addLayer(difEarthSciences);
	    
	    var difAeronomyAndAstrophysics = new ol.layer.Tile({
		title: "Astrophysics and Geospace Sciences",
		visible: false,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: 'Astro-Geo',
			transparent: true
		    }
		})
	    });
	    map.addLayer(difAeronomyAndAstrophysics);
	    
	    var difGlaciology = new ol.layer.Tile({
		title: "Glaciology",
		visible: false,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: 'Glacier',
			transparent: true
		    }
		})
	    });			  
	    map.addLayer(difGlaciology);
	    
	    var difOceanAndAtmosphericSciences = new ol.layer.Tile({
		title: "Ocean and Atmospheric Sciences",
		visible: false,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: 'Ocean-Atmosphere',
			transparent: true
		    }
		})
	    });							   
	    map.addLayer(difOceanAndAtmosphericSciences);
	    
	    var difOrganismsAndEcosystems = new ol.layer.Tile({
		title: "Organisms and Ecosystems",
		visible: false,
		source: new ol.source.TileWMS({
		    url: api_url,
		    params: {
			layers: 'Bio',
			transparent: true
		    }
		})
	    });
	    map.addLayer(difOrganismsAndEcosystems);

	    var layerSwitcher = new ol.control.LayerSwitcher({
	        tipLabel: 'Légende'
	    });
	    map.addControl(layerSwitcher);


		var styles = [
	        new ol.style.Style({
	          stroke: new ol.style.Stroke({
	            color: 'rgba(255, 0, 0, 0.8)',
	            width: 2
	          }),
	          fill: new ol.style.Fill({
	            color: 'rgba(255, 0, 0, 0.3)'
	          })
	        }),
			new ol.style.Style({
	          image: new ol.style.Circle({
	            radius: 4,
	           	stroke: new ol.style.Stroke({
		            color: 'rgba(255, 0, 0, 0.8)',
		            width: 2
		          }),
	            fill: new ol.style.Fill({
	              color: 'rgba(255, 0, 0, 0.3)'
	            })
	          })
	  		})
	    ];

		var geom;

		for (var i in extents) {
			var extent = extents[i];
			var north = extent.north;
			var east = extent.east;
			var west = extent.west;
			var south = extent.south;
		    // point
		    if (west == east && north == south) {
		    	geom = new ol.geom.Point(ol.proj.transform([west, north], 'EPSG:4326', 'EPSG:3031'));
		    } else {

		    // box
				geom = new ol.geom.Polygon([[
				  [west, north],
				  [east, north],
				  [east, south],
				  [west, south],
				  [west, north]
				]]).transform('EPSG:4326', 'EPSG:3031');

				[x0, y0] = ol.proj.fromLonLat([west, north], 'EPSG:3031');
				[x1, y1] = ol.proj.fromLonLat([east, south], 'EPSG:3031');
				var xmin = Math.min(x0, x1);
				var xmax = Math.max(x0, x1);
				var ymin = Math.min(y0, y1);
				var ymax = Math.max(y0, y1);

				if (!isNaN(xmin) && !isNaN(xmax) && !isNaN(ymin) && !isNaN(ymax) &&
					ol.extent.containsExtent(map.getView().calculateExtent(map.getSize()), [xmin, ymin, xmax, ymax])) {
					map.getView().fit([xmin, ymin, xmax, ymax], map.getSize());
				}
			}

		    feature = new ol.Feature({
		    	geometry: geom
		    });

		    var layer = new ol.layer.Vector({
		    	source: new ol.source.Vector({
		    		features: [feature]
		    	}),
		    	style: styles
		    });

			map.addLayer(layer);
		}

		var mousePosition = new ol.control.MousePosition({
	        coordinateFormat: ol.coordinate.createStringXY(2),
	        projection: 'EPSG:4326',
	        target: document.getElementById('mouseposition'),
	        undefinedHTML: '&nbsp;'
	    });
	    map.addControl(mousePosition);
	}


});
