let argv         = require('minimist')(process.argv.slice(2));
let autoprefixer = require('gulp-autoprefixer');
let cache        = require('gulp-cached');
let chmod        = require('gulp-chmod');
let concat       = require('gulp-concat');
let git          = require('gulp-git');
let gulp         = require('gulp');
let gulpif       = require('gulp-if');
let plumber      = require('gulp-plumber');
let pug          = require('gulp-pug');
let rename       = require('gulp-rename');
let sass         = require('gulp-sass');
let sourcemaps   = require('gulp-sourcemaps');
let uglify       = require('gulp-uglify-es').default;
let browserify   = require('browserify');
let babelify     = require('babelify');
let sourceStream = require('vinyl-source-stream');
let glob         = require('glob');
let es           = require('event-stream');
let path         = require('path');
let buffer       = require('vinyl-buffer');

let enabled = {
    chmod: argv.production,
    cleanup: argv.production,
    failCheck: argv.production,
    maps: argv.production,
    prettyPug: !argv.production,
    uglify: argv.production,
};

let destination = {
    css: 'flamenco/static/assets/css',
    pug: 'flamenco/templates',
    js: 'flamenco/static/assets/js/generated',
}


/* CSS */
gulp.task('styles', function(done) {
    gulp.src('src/styles/**/*.sass')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(sass({
            outputStyle: 'compressed'}
            ))
        .pipe(autoprefixer("last 3 versions"))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(gulp.dest(destination.css));
    done();
});


/* Templates - Pug */
gulp.task('templates', function(done) {
    gulp.src('src/templates/**/*.pug')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(cache('templating'))
        .pipe(pug({
            pretty: enabled.prettyPug
        }))
        .pipe(gulp.dest(destination.pug));
    done();
});


/* Individual Uglified Scripts */
gulp.task('scripts', function(done) {
    gulp.src('src/scripts/*.js')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(cache('scripting'))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(rename({suffix: '.min'}))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(gulpif(enabled.chmod, chmod(0o644)))
        .pipe(gulp.dest(destination.js));
    done();
});

function browserify_base(entry) {
    let pathSplited = path.dirname(entry).split(path.sep);
    let moduleName = pathSplited[pathSplited.length - 1];
    return browserify({
        entries: [entry],
        standalone: 'flamenco.' + moduleName,
    })
    .transform(babelify, { "presets": ["@babel/preset-env"] })
    .bundle()
    .pipe(gulpif(enabled.failCheck, plumber()))
    .pipe(sourceStream(path.basename(entry)))
    .pipe(buffer())
    .pipe(rename({
        basename: moduleName,
        extname: '.min.js'
    }));
}

function browserify_common() {
    return glob.sync('src/scripts/js/es6/common/**/init.js').map(browserify_base);
}

gulp.task('scripts_browserify', function(done) {
    glob('src/scripts/js/es6/individual/**/init.js', function(err, files) {
        if(err) done(err);

        let tasks = files.map(function(entry) {
            return browserify_base(entry)
            .pipe(gulpif(enabled.maps, sourcemaps.init()))
            .pipe(gulpif(enabled.uglify, uglify()))
            .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
            .pipe(gulp.dest(destination.js));
        });

        es.merge(tasks).on('end', done);
    })
});

/* Collection of scripts in src/scripts/tutti/ to merge into tutti.min.js */
/* Since it's always loaded, it's only for functions that we want site-wide */
gulp.task('scripts_tutti', function(done) {
	let toUglify = ['src/scripts/tutti/**/*.js']

	es.merge(gulp.src(toUglify), ...browserify_common())
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(concat("tutti.min.js"))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(gulpif(enabled.chmod, chmod(0o644)))
        .pipe(gulp.dest(destination.js));
    done();
});

/* Simply copy these vendor scripts from node_modules. */
gulp.task('scripts_copy_vendor', function(done) {
    let toCopy = [
        'node_modules/d3/build/d3.min.js',
        'node_modules/d3/build/d3.js',
        'node_modules/dagre-d3/dist/dagre-d3.min.js',
    ];

    gulp.src(toCopy)
        .pipe(gulp.dest(destination.js + '/vendor/'));
    done();
});


// While developing, run 'gulp watch'
gulp.task('watch',function(done) {
    gulp.watch('src/styles/**/*.sass',gulp.series('styles'));
    gulp.watch('src/templates/**/*.pug',gulp.series('templates'));
    gulp.watch('src/scripts/*.js',gulp.series('scripts'));
    gulp.watch('src/scripts/tutti/*.js',gulp.series('scripts_tutti'));
    gulp.watch('src/scripts/js/**/*.js', gulp.series('scripts_browserify', 'scripts_tutti'));
    done();
});

// Erases all generated files in output directories.
gulp.task('cleanup', function(done) {
    let paths = [];
    for (attr in destination) {
        paths.push(destination[attr]);
    }

    git.clean({ args: '-f -X ' + paths.join(' ') }, function (err) {
        if(err) throw err;
    });
    done();
});

// Run 'gulp' to build everything at once
let tasks = [];
if (enabled.cleanup) tasks.push('cleanup');
gulp.task('default', gulp.parallel(tasks.concat([
    'styles',
    'templates',
    'scripts',
    'scripts_tutti',
    'scripts_copy_vendor',
])));
